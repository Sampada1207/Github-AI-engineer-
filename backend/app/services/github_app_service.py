import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from jose import jwt
from app.config import settings


class GitHubAppService:
    """
    Service for GitHub App authentication, JWT token generation, and
    installation access token management.
    """

    def __init__(self):
        self._token_cache: Dict[str, Dict[str, Any]] = {}

    def is_configured(self) -> bool:
        """Returns True if GitHub App ID and Private Key are configured."""
        app_id = settings.GITHUB_APP_ID
        key = settings.GITHUB_APP_PRIVATE_KEY
        return bool(app_id and app_id.strip() and key and key.strip())

    def _clean_private_key(self, raw_key: str) -> str:

        """Normalizes PEM formatting for RSA Private Key."""
        key = raw_key.strip()
        # Handle unescaped newlines in environment variable
        if "\\n" in key:
            key = key.replace("\\n", "\n")
        return key

    def generate_app_jwt(self) -> str:
        """
        Generates an RS256-signed JWT for GitHub App authentication.
        Valid for 10 minutes (GitHub maximum limit).
        """
        if not self.is_configured():
            raise ValueError("GitHub App configuration is missing or disabled. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.")

        app_id = settings.GITHUB_APP_ID.strip()
        raw_key = settings.GITHUB_APP_PRIVATE_KEY
        pem_key = self._clean_private_key(raw_key)

        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago to handle clock skew
            "exp": now + (9 * 60),  # Expires in 9 minutes
            "iss": app_id
        }

        try:
            token = jwt.encode(payload, pem_key, algorithm="RS256")
            return token
        except Exception as e:
            raise ValueError(f"Failed to generate GitHub App JWT signature: {str(e)}")

    def get_installation_token(self, installation_id: Optional[str] = None) -> str:
        """
        Fetches an installation access token for a given installation ID or from config.
        Caches tokens until near expiration.
        """
        inst_id = installation_id or settings.GITHUB_APP_INSTALLATION_ID
        if not inst_id or not str(inst_id).strip():
            raise ValueError("GitHub App installation ID is required.")

        inst_id = str(inst_id).strip()

        # Check cache (valid if more than 60s remain)
        now = time.time()
        cached = self._token_cache.get(inst_id)
        if cached and cached.get("expires_at", 0) > now + 60:
            return cached["token"]

        app_jwt = self.generate_app_jwt()
        url = f"https://api.github.com/app/installations/{inst_id}/access_tokens"

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-AI-Engineer/1.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                token = data.get("token")
                expires_at_str = data.get("expires_at")
                
                # Default cache duration: 50 minutes (tokens last 1 hour)
                expires_at = now + (50 * 60)
                self._token_cache[inst_id] = {
                    "token": token,
                    "expires_at": expires_at
                }
                return token
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise ValueError(f"GitHub App token fetch failed (HTTP {e.code}): {err_body}")
        except Exception as ex:
            raise ValueError(f"Failed to connect to GitHub App API: {str(ex)}")


github_app_service = GitHubAppService()
