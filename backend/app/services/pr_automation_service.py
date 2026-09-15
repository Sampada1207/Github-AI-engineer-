import hmac
import hashlib
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import WebhookEventLog, Repository
from app.repositories import crud
from app.services.github_service import github_service
from app.services.diff_service import git_diff_service
from app.schemas.schemas import AutomatedPRReviewResponse


class PRAutomationService:
    """
    Service to validate GitHub webhook signatures, parse PR event payloads,
    enforce idempotency, and execute automated PR reviews in DRY-RUN mode.
    """

    SUPPORTED_ACTIONS = {"opened", "synchronize", "reopened"}

    def verify_webhook_signature(self, body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verifies X-Hub-Signature-256 header using constant-time comparison (hmac.compare_digest).
        """
        secret = settings.GITHUB_WEBHOOK_SECRET
        if not secret or not secret.strip():
            # If secret is unconfigured in dev/test, return True unless signature is present and bad
            if not signature_header:
                return True
            secret = "dev_secret"

        if not signature_header:
            return False

        if not signature_header.startswith("sha256="):
            return False

        expected_sig = signature_header[7:]
        mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
        calculated_sig = mac.hexdigest()

        return hmac.compare_digest(calculated_sig, expected_sig)

    def extract_pr_event(self, payload: Dict[str, Any], delivery_id: Optional[str] = None) -> Tuple[str, str, int, str, str, str, str]:
        """
        Extracts repository owner, repository name, PR number, action, head sha, base ref, and event ID.
        """
        repo_data = payload.get("repository") or {}
        owner_data = repo_data.get("owner") or {}
        pr_data = payload.get("pull_request") or {}

        owner = owner_data.get("login") or ""
        repo_name = repo_data.get("name") or ""
        pr_number = payload.get("number") or pr_data.get("number") or 0
        action = payload.get("action") or ""
        head_data = pr_data.get("head") or {}
        base_data = pr_data.get("base") or {}
        head_sha = head_data.get("sha") or ""
        base_ref = base_data.get("ref") or "main"
        head_ref = head_data.get("ref") or "head"

        if not owner or not repo_name:
            raise ValueError("Webhook payload is missing repository owner or name.")
        if not pr_number or pr_number <= 0:
            raise ValueError("Webhook payload is missing valid pull_request number.")

        owner, repo_name = github_service.validate_owner_repo(owner, repo_name)

        event_id = delivery_id or f"evt_{owner}_{repo_name}_{pr_number}_{head_sha[:8]}_{action}"
        return owner, repo_name, pr_number, action, head_sha, base_ref, event_id

    def process_webhook_pr_event(
        self,
        db: Session,
        payload: Dict[str, Any],
        delivery_id: Optional[str] = None
    ) -> AutomatedPRReviewResponse:
        """
        Processes a pull_request webhook event. Checks idempotency, mode, and executes PR review.
        """
        try:
            owner, repo_name, pr_number, action, head_sha, base_ref, event_id = self.extract_pr_event(payload, delivery_id)
        except ValueError as ve:
            return AutomatedPRReviewResponse(
                status="error",
                repository="unknown",
                pull_request_number=0,
                action="unknown",
                review_triggered=False,
                dry_run=True,
                summary=f"Payload validation failed: {str(ve)}",
                findings_count=0
            )

        repo_slug = f"{owner}/{repo_name}"

        # 1. Check Action Support
        if action not in self.SUPPORTED_ACTIONS:
            self._log_event(db, event_id=event_id, event_type="pull_request", action=action, repo=repo_slug, pr_num=pr_number, status="ignored", summary=f"Action '{action}' is not configured for automated review.")
            return AutomatedPRReviewResponse(
                status="ignored",
                repository=repo_slug,
                pull_request_number=pr_number,
                action=action,
                review_triggered=False,
                dry_run=True,
                summary=f"Ignored action '{action}'. Only opened, synchronize, reopened are processed.",
                findings_count=0
            )

        # 2. Check Idempotency / Duplicate Delivery
        existing_log = db.query(WebhookEventLog).filter(WebhookEventLog.event_id == event_id).first()
        if existing_log:
            return AutomatedPRReviewResponse(
                status=existing_log.status,
                repository=repo_slug,
                pull_request_number=pr_number,
                action=action,
                review_triggered=(existing_log.status == "dry-run"),
                dry_run=True,
                summary=f"Duplicate event delivery handled cleanly. Status: {existing_log.status}",
                findings_count=existing_log.findings_count
            )

        # 3. Check Automation Mode
        mode = settings.GITHUB_PR_AUTOMATION_MODE.lower()
        if mode == "disabled" or not settings.GITHUB_APP_ENABLED and mode != "dry-run":
            self._log_event(db, event_id=event_id, event_type="pull_request", action=action, repo=repo_slug, pr_num=pr_number, status="disabled", summary="PR Automation mode is disabled.")
            return AutomatedPRReviewResponse(
                status="disabled",
                repository=repo_slug,
                pull_request_number=pr_number,
                action=action,
                review_triggered=False,
                dry_run=True,
                summary="Automation is disabled via GITHUB_PR_AUTOMATION_MODE config.",
                findings_count=0
            )

        # 4. Execute Complete PR Review Pipeline in DRY-RUN Mode
        try:
            pr_info = github_service.get_pull_request(owner, repo_name, pr_number)
            diff_text = github_service.get_pull_request_diff(owner, repo_name, pr_number)

            # Match repository files in DB if available
            files_data = []
            db_repo = db.query(Repository).filter(
                (Repository.url.ilike(f"%{repo_slug}%")) | (Repository.name.ilike(repo_name))
            ).first()

            if db_repo:
                db_files = crud.get_files_by_repo(db, db_repo.id)
                files_data = [{"path": f.path, "name": f.name, "language": f.language, "size": f.size, "content": f.content} for f in db_files]

            target_repo_id = db_repo.id if db_repo else f"gh-{owner}-{repo_name}"

            if not diff_text or not diff_text.strip():
                review_res = {
                    "ai_review": {
                        "summary": {"diff_summary": "No code diff changes detected in PR.", "findings_count": 0},
                        "findings": []
                    }
                }
            else:
                review_res = git_diff_service.review_diff(
                    repo_id=target_repo_id,
                    base_revision=pr_info["base_ref"],
                    target_revision=pr_info["head_ref"],
                    diff_text=diff_text,
                    files_data=files_data
                )

            summary_str = github_service.format_github_review_summary(pr_info, review_res)
            ai_review = review_res.get("ai_review") or {}
            findings = ai_review.get("findings") or []
            findings_cnt = len(findings)

            self._log_event(
                db=db,
                event_id=event_id,
                event_type="pull_request",
                action=action,
                repo=repo_slug,
                pr_num=pr_number,
                status="dry-run",
                summary=summary_str,
                findings_cnt=findings_cnt
            )

            return AutomatedPRReviewResponse(
                status="dry-run",
                repository=repo_slug,
                pull_request_number=pr_number,
                action=action,
                review_triggered=True,
                dry_run=True,
                summary=summary_str,
                findings_count=findings_cnt
            )

        except Exception as ex:
            err_msg = f"Automated PR Review execution failed: {str(ex)}"
            self._log_event(db, event_id=event_id, event_type="pull_request", action=action, repo=repo_slug, pr_num=pr_number, status="failed", summary=err_msg)
            return AutomatedPRReviewResponse(
                status="failed",
                repository=repo_slug,
                pull_request_number=pr_number,
                action=action,
                review_triggered=False,
                dry_run=True,
                summary=err_msg,
                findings_count=0
            )

    def _log_event(
        self,
        db: Session,
        event_id: str,
        event_type: str,
        action: str,
        repo: str,
        pr_num: int,
        status: str,
        summary: str,
        findings_cnt: int = 0
    ):
        try:
            log = WebhookEventLog(
                event_id=event_id,
                event_type=event_type,
                action=action,
                repository=repo,
                pr_number=pr_num,
                status=status,
                summary=summary,
                findings_count=findings_cnt
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()


pr_automation_service = PRAutomationService()
