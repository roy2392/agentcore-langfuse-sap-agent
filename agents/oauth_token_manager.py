"""
OAuth Token Manager for Cognito Client Credentials Flow

This module provides token management for accessing AgentCore Gateway with
OAuth 2.0 client credentials authentication.
"""

import httpx
import time
from typing import Optional, Dict
import base64
import os


class OAuthTokenManager:
    """Manages OAuth tokens with automatic refresh for Gateway access"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cognito_domain: str,
        region: str = "us-east-1"
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"https://{cognito_domain}.auth.{region}.amazoncognito.com/oauth2/token"

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        print(f"[OAuth] Initialized token manager for domain: {cognito_domain}")

    def get_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            str: Valid Bearer token for Authorization header
        """
        # Check if we have a valid cached token
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # Token expired or doesn't exist, fetch new one
        print("[OAuth] Fetching new access token from Cognito...")
        self._fetch_token()

        return self._access_token

    def _fetch_token(self) -> None:
        """Fetch a new access token using client credentials flow"""

        # Encode client credentials for Basic Auth
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": "sap-gateway-prd/tools.invoke"  # Custom resource server scope for Gateway
        }

        try:
            response = httpx.post(
                self.token_url,
                headers=headers,
                data=data,
                timeout=10.0
            )
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)

            # Set expiration with 60-second buffer
            self._token_expires_at = time.time() + expires_in - 60

            print(f"[OAuth] Successfully obtained token, expires in {expires_in}s")

        except httpx.HTTPError as e:
            error_msg = f"Failed to fetch OAuth token: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse: {e.response.text}"
            print(f"[OAuth] ERROR: {error_msg}")
            raise ValueError(error_msg)


def create_token_manager_from_env() -> Optional[OAuthTokenManager]:
    """
    Create OAuth token manager from environment variables.

    Expected environment variables:
    - COGNITO_CLIENT_ID
    - COGNITO_CLIENT_SECRET
    - COGNITO_DOMAIN
    - AWS_DEFAULT_REGION (optional, defaults to us-east-1)

    Returns:
        OAuthTokenManager if all credentials are present, None otherwise
    """
    client_id = os.getenv("COGNITO_CLIENT_ID")
    client_secret = os.getenv("COGNITO_CLIENT_SECRET")
    cognito_domain = os.getenv("COGNITO_DOMAIN")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not all([client_id, client_secret, cognito_domain]):
        print("[OAuth] WARNING: Missing Cognito credentials in environment variables")
        print(f"[OAuth]   COGNITO_CLIENT_ID: {'✓' if client_id else '✗'}")
        print(f"[OAuth]   COGNITO_CLIENT_SECRET: {'✓' if client_secret else '✗'}")
        print(f"[OAuth]   COGNITO_DOMAIN: {'✓' if cognito_domain else '✗'}")
        return None

    return OAuthTokenManager(
        client_id=client_id,
        client_secret=client_secret,
        cognito_domain=cognito_domain,
        region=region
    )
