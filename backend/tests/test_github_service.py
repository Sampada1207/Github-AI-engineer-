import json
import pytest
from unittest.mock import patch, MagicMock

from app.config import settings
from app.services.github_service import github_service, GitHubService


def test_github_owner_repo_validation():
    owner, repo = github_service.validate_owner_repo("octocat", "Spoon-Knife.git")
    assert owner == "octocat"
    assert repo == "Spoon-Knife"

    owner, repo = github_service.validate_owner_repo("  facebook ", "react ")
    assert owner == "facebook"
    assert repo == "react"

    with pytest.raises(ValueError, match="Invalid GitHub owner format"):
        github_service.validate_owner_repo("octocat; rm -rf", "repo")

    with pytest.raises(ValueError, match="Invalid GitHub repository name format"):
        github_service.validate_owner_repo("octocat", "repo|bad")


def test_extract_owner_repo():
    owner, repo = github_service.extract_owner_repo("https://github.com/octocat/Spoon-Knife.git")
    assert owner == "octocat"
    assert repo == "Spoon-Knife"

    owner, repo = github_service.extract_owner_repo("octocat/Spoon-Knife")
    assert owner == "octocat"
    assert repo == "Spoon-Knife"

    owner, repo = github_service.extract_owner_repo("git@github.com:torvalds/linux.git")
    assert owner == "torvalds"
    assert repo == "linux"

    with pytest.raises(ValueError, match="Could not parse valid GitHub owner"):
        github_service.extract_owner_repo("invalid-github-url-without-slash")


def test_github_headers():
    with patch.object(settings, "GITHUB_TOKEN", "mock-token-123"):
        headers = github_service._get_headers()
        assert headers["Authorization"] == "Bearer mock-token-123"
        assert "GitHub-AI-Engineer" in headers["User-Agent"]

    with patch.object(settings, "GITHUB_TOKEN", None):
        headers = github_service._get_headers()
        assert "Authorization" not in headers


def test_get_pull_request_success():
    mock_pr_response = {
        "id": 123456,
        "number": 42,
        "title": "Fix authentication bug",
        "state": "open",
        "body": "Resolves auth crash when token expires.",
        "user": {"login": "dev_user"},
        "html_url": "https://github.com/octocat/Spoon-Knife/pull/42",
        "head": {"ref": "fix-auth", "sha": "abc1234"},
        "base": {"ref": "main", "sha": "xyz9876"},
        "draft": False,
        "merged": False,
        "created_at": "2026-09-15T20:00:00Z",
        "updated_at": "2026-09-15T21:00:00Z",
        "additions": 15,
        "deletions": 3,
        "changed_files": 2
    }

    with patch.object(github_service, "_make_request") as mock_req:
        mock_req.return_value = (200, json.dumps(mock_pr_response).encode("utf-8"))
        res = github_service.get_pull_request("octocat", "Spoon-Knife", 42)

        assert res["number"] == 42
        assert res["title"] == "Fix authentication bug"
        assert res["author"] == "dev_user"
        assert res["additions"] == 15
        assert res["deletions"] == 3


def test_get_pull_request_invalid_pr_number():
    with pytest.raises(ValueError, match="PR number must be a positive integer"):
        github_service.get_pull_request("octocat", "Spoon-Knife", -1)

    with pytest.raises(ValueError, match="PR number must be a positive integer"):
        github_service.get_pull_request("octocat", "Spoon-Knife", 0)


def test_format_github_review_summary():
    pr_info = {
        "title": "Add diff analysis",
        "number": 10,
        "author": "tester",
        "state": "open",
        "html_url": "https://github.com/org/repo/pull/10"
    }

    diff_review = {
        "total_files_changed": 1,
        "total_additions": 20,
        "total_deletions": 5,
        "changed_symbols": ["review_diff"],
        "impact_analysis": {
            "blast_radius_score": 35,
            "impact_risk": "Medium",
            "affected_files": ["services/diff_service.py"],
            "affected_symbols": ["git_diff_service"]
        },
        "ai_review": {
            "summary": {
                "diff_summary": "Added review_diff method.",
                "severity_breakdown": {"Critical": 0, "High": 1, "Medium": 0, "Low": 0, "Info": 0}
            },
            "findings": [
                {
                    "severity": "High",
                    "category": "Security",
                    "file": "services/diff_service.py",
                    "explanation": "Ensure git revisions are validated.",
                    "suggested_fix": "validate_revision(rev)"
                }
            ]
        }
    }

    summary = github_service.format_github_review_summary(pr_info, diff_review)
    assert "AI Code Review Summary for PR #10" in summary
    assert "High" in summary
    assert "services/diff_service.py" in summary


def test_github_service_error_handling():
    with patch.object(github_service, "_make_request") as mock_req:
        mock_req.side_effect = ValueError("GitHub resource not found or repository is private/unaccessible.")
        with pytest.raises(ValueError, match="not found"):
            github_service.get_pull_request("owner", "repo", 999)

    with patch.object(github_service, "_make_request") as mock_req:
        mock_req.side_effect = ValueError("GitHub API rate limit exceeded.")
        with pytest.raises(ValueError, match="rate limit"):
            github_service.get_repo_info("owner", "repo")

