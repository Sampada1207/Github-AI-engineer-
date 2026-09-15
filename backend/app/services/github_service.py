import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings


class GitHubService:
    """
    Service for secure GitHub REST API integrations.
    Fetches PR metadata, diffs, changed files, and repository details.
    """

    GITHUB_API_BASE = "https://api.github.com"

    def validate_owner_repo(self, owner: str, repo: str) -> Tuple[str, str]:
        """
        Validates owner and repository name against strict alphanumeric + dash/underscore/dot rules
        to prevent SSRF, path traversal, or command injection.
        """
        if not owner or not isinstance(owner, str):
            raise ValueError("GitHub repository owner must be a non-empty string.")
        if not repo or not isinstance(repo, str):
            raise ValueError("GitHub repository name must be a non-empty string.")

        owner_clean = owner.strip()
        repo_clean = repo.strip()

        # Remove trailing .git if provided in repo name
        if repo_clean.endswith(".git"):
            repo_clean = repo_clean[:-4]

        pattern = r"^[a-zA-Z0-9_.\-]+$"
        if not re.match(pattern, owner_clean):
            raise ValueError("Invalid GitHub owner format.")
        if not re.match(pattern, repo_clean):
            raise ValueError("Invalid GitHub repository name format.")

        return owner_clean, repo_clean

    def extract_owner_repo(self, input_str: str) -> Tuple[str, str]:
        """
        Extracts (owner, repo) from GitHub URL, SSH format, or 'owner/repo' format.
        Examples:
          - 'https://github.com/octocat/Spoon-Knife.git' -> ('octocat', 'Spoon-Knife')
          - 'octocat/Spoon-Knife' -> ('octocat', 'Spoon-Knife')
          - 'git@github.com:octocat/Spoon-Knife.git' -> ('octocat', 'Spoon-Knife')
        """
        if not input_str or not isinstance(input_str, str):
            raise ValueError("Repository identifier or URL cannot be empty.")

        input_str = input_str.strip()

        # Match HTTPS URL
        https_match = re.search(r"github\.com/([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+?)(?:\.git|/)?$", input_str)
        if https_match:
            return self.validate_owner_repo(https_match.group(1), https_match.group(2))

        # Match SSH URL
        ssh_match = re.search(r"git@github\.com:([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+?)(?:\.git)?$", input_str)
        if ssh_match:
            return self.validate_owner_repo(ssh_match.group(1), ssh_match.group(2))

        # Match owner/repo
        parts = [p for p in input_str.split("/") if p]
        if len(parts) == 2:
            return self.validate_owner_repo(parts[0], parts[1])

        raise ValueError(f"Could not parse valid GitHub owner and repository from '{input_str}'.")

    def _get_headers(self, accept_header: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        headers = {
            "User-Agent": "GitHub-AI-Engineer/1.0",
            "Accept": accept_header
        }
        token = settings.GITHUB_TOKEN
        if token and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        return headers

    def _make_request(self, url: str, accept_header: str = "application/vnd.github.v3+json") -> Tuple[int, bytes]:
        """
        Executes a secure HTTPS request strictly against api.github.com.
        """
        if not url.startswith(self.GITHUB_API_BASE):
            raise ValueError("Security Violation: Requests outside api.github.com are rejected.")

        headers = self._get_headers(accept_header)
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status_code = resp.getcode()
                content = resp.read()
                return status_code, content
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            status_code = e.code

            if status_code == 404:
                raise ValueError("GitHub resource not found or repository is private/unaccessible.")
            elif status_code == 401:
                raise ValueError("Unauthorized GitHub API access. Please check your GITHUB_TOKEN.")
            elif status_code == 403:
                if "rate limit" in error_body.lower():
                    raise ValueError("GitHub API rate limit exceeded. Please configure a valid GITHUB_TOKEN.")
                raise ValueError("GitHub API access forbidden or rate limited.")
            elif status_code == 422:
                raise ValueError("Invalid parameters sent to GitHub API.")
            else:
                raise ValueError(f"GitHub API error (HTTP {status_code}).")
        except urllib.error.URLError as ue:
            raise ValueError(f"Failed to connect to GitHub API: {ue.reason}")
        except Exception as ex:
            raise ValueError(f"GitHub API connection failure: {str(ex)}")

    def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Fetches repository details from GitHub API.
        """
        owner, repo = self.validate_owner_repo(owner, repo)
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}"
        _, content = self._make_request(url)
        return json.loads(content.decode("utf-8"))

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetches Pull Request metadata for a specific PR number.
        """
        owner, repo = self.validate_owner_repo(owner, repo)
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise ValueError("PR number must be a positive integer.")

        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            _, content = self._make_request(url)
            data = json.loads(content.decode("utf-8"))
        except ValueError as ve:
            if "not found" in str(ve).lower():
                raise ValueError(f"Pull Request #{pr_number} not found in '{owner}/{repo}'.")
            raise

        user_info = data.get("user") or {}
        head_info = data.get("head") or {}
        base_info = data.get("base") or {}

        return {
            "id": data.get("id"),
            "number": data.get("number"),
            "title": data.get("title", ""),
            "state": data.get("state", "unknown"),
            "body": data.get("body") or "",
            "author": user_info.get("login", "unknown"),
            "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
            "base_ref": base_info.get("ref", "main"),
            "head_ref": head_info.get("ref", "head"),
            "head_sha": head_info.get("sha", ""),
            "base_sha": base_info.get("sha", ""),
            "draft": data.get("draft", False),
            "merged": data.get("merged", False),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
            "changed_files": data.get("changed_files", 0)
        }

    def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Fetches raw unified diff text for a Pull Request.
        """
        owner, repo = self.validate_owner_repo(owner, repo)
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise ValueError("PR number must be a positive integer.")

        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        _, content = self._make_request(url, accept_header="application/vnd.github.v3.diff")
        diff_str = content.decode("utf-8", errors="replace")
        return diff_str

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetches changed files array for a Pull Request.
        """
        owner, repo = self.validate_owner_repo(owner, repo)
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise ValueError("PR number must be a positive integer.")

        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        _, content = self._make_request(url)
        data = json.loads(content.decode("utf-8"))
        
        files = []
        for f in data:
            files.append({
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "patch": f.get("patch", "")
            })
        return files

    def format_github_review_summary(self, pr_info: Dict[str, Any], diff_review: Dict[str, Any]) -> str:
        """
        Formats a clean, publication-ready Markdown review summary suitable for posting
        as a GitHub PR review.
        """
        title = pr_info.get("title", "Pull Request")
        pr_num = pr_info.get("number", 0)
        author = pr_info.get("author", "author")
        state = pr_info.get("state", "open")
        url = pr_info.get("html_url", "")

        ai_review = diff_review.get("ai_review") or {}
        summary = ai_review.get("summary") or {}
        findings = ai_review.get("findings") or []
        impact = diff_review.get("impact_analysis") or {}

        severity_breakdown = summary.get("severity_breakdown") or {}
        diff_summary = summary.get("diff_summary") or "PR code changes analyzed."
        blast_score = impact.get("blast_radius_score", 0)
        risk_level = impact.get("impact_risk", "Low")
        affected_files = impact.get("affected_files") or []
        affected_symbols = impact.get("affected_symbols") or []

        lines = []
        lines.append(f"## 🤖 AI Code Review Summary for PR #{pr_num}: {title}")
        lines.append(f"**Author:** @{author} | **Status:** `{state.upper()}` | **PR Link:** [{pr_num}]({url})\n")
        lines.append("### 📊 Overview & Impact")
        lines.append(f"- **Summary:** {diff_summary}")
        lines.append(f"- **Blast Radius Score:** `{blast_score}/100` ({risk_level} Risk)")
        lines.append(f"- **Files Changed:** {diff_review.get('total_files_changed', 0)} (+{diff_review.get('total_additions', 0)} / -{diff_review.get('total_deletions', 0)})")
        lines.append(f"- **Downstream Impacted Files:** {len(affected_files)}")
        lines.append(f"- **Impacted Symbols:** {len(affected_symbols)}\n")

        lines.append("### 🎯 Severity Breakdown")
        crit = severity_breakdown.get("Critical", 0)
        high = severity_breakdown.get("High", 0)
        med = severity_breakdown.get("Medium", 0)
        low = severity_breakdown.get("Low", 0)
        info = severity_breakdown.get("Info", 0)
        lines.append(f"- 🔴 **Critical:** {crit} | 🟧 **High:** {high} | 🟨 **Medium:** {med} | 🟦 **Low:** {low} | ℹ️ **Info:** {info}\n")

        if findings:
            lines.append("### 🔍 Key Findings & Suggestions")
            for idx, finding in enumerate(findings[:10], 1):
                sev = finding.get("severity", "Medium")
                cat = finding.get("category", "General")
                file_path = finding.get("file", "file")
                explanation = finding.get("explanation", "")
                fix = finding.get("suggested_fix")

                lines.append(f"#### {idx}. [{sev.upper()}] {cat} - `{file_path}`")
                lines.append(f"{explanation}")
                if fix:
                    lines.append(f"**Suggested Fix:**\n```suggestion\n{fix}\n```")
                lines.append("")
        else:
            lines.append("### ✅ No Critical Code Smells or Security Issues Detected!\n")

        lines.append("---\n*Generated by GitHub AI Engineer Intelligence Pipeline.*")
        return "\n".join(lines)


github_service = GitHubService()
