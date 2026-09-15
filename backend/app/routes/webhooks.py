from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.repositories import crud
from app.routes.deps import get_current_user
from app.models.models import User, WebhookEventLog, Repository
from app.schemas.schemas import (
    AutomatedPRReviewResponse,
    WebhookLogResponse
)
from app.services.pr_automation_service import pr_automation_service
from app.services.github_app_service import github_app_service

router = APIRouter(tags=["webhooks_and_automations"])


@router.post("/api/webhooks/github", response_model=AutomatedPRReviewResponse)
@router.post("/webhooks/github", response_model=AutomatedPRReviewResponse)
async def github_webhook_endpoint(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    db: Session = Depends(get_db)
):
    """
    Receives and processes incoming GitHub Webhook events.
    Verifies HMAC SHA-256 signatures, checks event action support, and triggers
    the automated PR intelligence review pipeline in DRY-RUN mode.
    """
    raw_body = await request.body()

    # 1. Signature Verification
    if not pr_automation_service.verify_webhook_signature(raw_body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Hub-Signature-256 webhook signature."
        )

    # 2. Event Type Check
    if not x_github_event or x_github_event != "pull_request":
        return AutomatedPRReviewResponse(
            status="ignored",
            repository="unknown",
            pull_request_number=0,
            action=x_github_event or "unknown",
            review_triggered=False,
            dry_run=True,
            summary=f"Event '{x_github_event}' ignored. Only 'pull_request' events are supported.",
            findings_count=0
        )

    # 3. Parse JSON Payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed or invalid JSON payload."
        )

    # 4. Process PR Event in DRY-RUN mode
    res = pr_automation_service.process_webhook_pr_event(
        db=db,
        payload=payload,
        delivery_id=x_github_delivery
    )
    return res


@router.get("/api/webhooks/logs", response_model=List[WebhookLogResponse])
def get_recent_webhook_logs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches recent GitHub webhook execution logs across repositories."""
    logs = db.query(WebhookEventLog).order_by(WebhookEventLog.created_at.desc()).limit(limit).all()
    return logs


@router.get("/api/repositories/{repo_id}/pull-requests/automations", response_model=List[WebhookLogResponse])
def get_repository_automation_logs(
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches recent automated PR review execution logs for a specific repository."""
    repo = crud.get_repo_by_id(db, repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    logs = db.query(WebhookEventLog).filter(
        WebhookEventLog.repository.ilike(f"%{repo.name}%") | WebhookEventLog.repository.ilike(f"%{repo.url}%")
    ).order_by(WebhookEventLog.created_at.desc()).limit(20).all()

    return logs


@router.get("/api/webhooks/status")
def get_github_app_automation_status():
    """Returns current GitHub App and PR Automation configuration status."""
    return {
        "github_app_configured": github_app_service.is_configured(),
        "automation_mode": settings.GITHUB_PR_AUTOMATION_MODE,
        "app_enabled": settings.GITHUB_APP_ENABLED,
        "webhook_secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET and settings.GITHUB_WEBHOOK_SECRET.strip())
    }
