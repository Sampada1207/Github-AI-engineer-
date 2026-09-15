import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.pr_automation_service import pr_automation_service
from app.services.github_app_service import github_app_service
from app.services.github_service import github_service

client = TestClient(app)


def test_webhook_signature_verification_valid():
    secret = "test_webhook_secret_key_123"
    body = b'{"action":"opened","number":1}'
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    valid_header = f"sha256={mac.hexdigest()}"

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        assert pr_automation_service.verify_webhook_signature(body, valid_header) is True


def test_webhook_signature_verification_invalid():
    secret = "test_webhook_secret_key_123"
    body = b'{"action":"opened","number":1}'
    invalid_header = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        assert pr_automation_service.verify_webhook_signature(body, invalid_header) is False
        assert pr_automation_service.verify_webhook_signature(body, None) is False


def test_webhook_unsupported_pr_action():
    payload = {
        "action": "closed",
        "number": 10,
        "repository": {"name": "Spoon-Knife", "owner": {"login": "octocat"}},
        "pull_request": {"number": 10, "head": {"sha": "def456"}, "base": {"ref": "main"}}
    }
    body = json.dumps(payload).encode("utf-8")
    secret = "test_secret"
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    sig_header = f"sha256={mac.hexdigest()}"

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = client.post(
            "/api/webhooks/github",
            data=body,
            headers={
                "X-Hub-Signature-256": sig_header,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-closed-1"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ignored"
        assert data["pull_request_number"] == 10
        assert data["review_triggered"] is False


def test_webhook_pr_opened_event_dry_run():
    payload = {
        "action": "opened",
        "number": 15,
        "repository": {"name": "Spoon-Knife", "owner": {"login": "octocat"}},
        "pull_request": {
            "number": 15,
            "title": "Fix memory leak",
            "html_url": "https://github.com/octocat/Spoon-Knife/pull/15",
            "head": {"ref": "fix-mem", "sha": "12345678"},
            "base": {"ref": "main"}
        }
    }
    body = json.dumps(payload).encode("utf-8")
    secret = "test_secret"
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    sig_header = f"sha256={mac.hexdigest()}"

    mock_pr = {
        "number": 15,
        "title": "Fix memory leak",
        "author": "octocat",
        "state": "open",
        "base_ref": "main",
        "head_ref": "fix-mem",
        "html_url": "https://github.com/octocat/Spoon-Knife/pull/15",
        "additions": 10,
        "deletions": 2,
        "changed_files": 1
    }

    mock_diff = "diff --git a/main.py b/main.py\n--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,3 @@\n+print('hello')\n"

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret), \
         patch.object(settings, "GITHUB_PR_AUTOMATION_MODE", "dry-run"), \
         patch.object(github_service, "get_pull_request", return_value=mock_pr), \
         patch.object(github_service, "get_pull_request_diff", return_value=mock_diff):

        res = client.post(
            "/api/webhooks/github",
            data=body,
            headers={
                "X-Hub-Signature-256": sig_header,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-open-15"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "dry-run"
        assert data["dry_run"] is True
        assert data["review_triggered"] is True
        assert data["pull_request_number"] == 15
        assert "AI Code Review Summary for PR #15" in data["summary"]


def test_webhook_pr_synchronize_and_reopened_events():
    for act in ["synchronize", "reopened"]:
        payload = {
            "action": act,
            "number": 20,
            "repository": {"name": "Spoon-Knife", "owner": {"login": "octocat"}},
            "pull_request": {
                "number": 20,
                "title": "Update docs",
                "html_url": "https://github.com/octocat/Spoon-Knife/pull/20",
                "head": {"ref": "docs-update", "sha": f"sha-{act}-99"},
                "base": {"ref": "main"}
            }
        }
        body = json.dumps(payload).encode("utf-8")
        secret = "test_secret"
        mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
        sig_header = f"sha256={mac.hexdigest()}"

        mock_pr = {
            "number": 20,
            "title": "Update docs",
            "author": "octocat",
            "state": "open",
            "base_ref": "main",
            "head_ref": "docs-update",
            "html_url": "https://github.com/octocat/Spoon-Knife/pull/20",
            "additions": 5,
            "deletions": 0,
            "changed_files": 1
        }

        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret), \
             patch.object(settings, "GITHUB_PR_AUTOMATION_MODE", "dry-run"), \
             patch.object(github_service, "get_pull_request", return_value=mock_pr), \
             patch.object(github_service, "get_pull_request_diff", return_value=""):

            res = client.post(
                "/api/webhooks/github",
                data=body,
                headers={
                    "X-Hub-Signature-256": sig_header,
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": f"deliv-{act}-20"
                }
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "dry-run"
            assert data["action"] == act


def test_webhook_duplicate_delivery_idempotency():
    payload = {
        "action": "opened",
        "number": 30,
        "repository": {"name": "Spoon-Knife", "owner": {"login": "octocat"}},
        "pull_request": {
            "number": 30,
            "title": "Test idempotency",
            "head": {"ref": "test", "sha": "sha30"},
            "base": {"ref": "main"}
        }
    }
    body = json.dumps(payload).encode("utf-8")
    secret = "test_secret"
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    sig_header = f"sha256={mac.hexdigest()}"

    mock_pr = {
        "number": 30,
        "title": "Test idempotency",
        "author": "octocat",
        "state": "open",
        "base_ref": "main",
        "head_ref": "test",
        "html_url": "https://github.com/octocat/Spoon-Knife/pull/30",
        "additions": 1,
        "deletions": 1,
        "changed_files": 1
    }

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret), \
         patch.object(settings, "GITHUB_PR_AUTOMATION_MODE", "dry-run"), \
         patch.object(github_service, "get_pull_request", return_value=mock_pr), \
         patch.object(github_service, "get_pull_request_diff", return_value=""):

        delivery_id = "duplicate-delivery-id-777"
        # First call
        res1 = client.post(
            "/api/webhooks/github",
            data=body,
            headers={
                "X-Hub-Signature-256": sig_header,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": delivery_id
            }
        )
        assert res1.status_code == 200

        # Duplicate call
        res2 = client.post(
            "/api/webhooks/github",
            data=body,
            headers={
                "X-Hub-Signature-256": sig_header,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": delivery_id
            }
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert "Duplicate event delivery handled cleanly" in data2["summary"]


def test_github_app_unconfigured_error():
    with patch.object(settings, "GITHUB_APP_ID", None), \
         patch.object(settings, "GITHUB_APP_PRIVATE_KEY", None):
        assert github_app_service.is_configured() is False
        with pytest.raises(ValueError, match="GitHub App configuration is missing"):
            github_app_service.generate_app_jwt()
