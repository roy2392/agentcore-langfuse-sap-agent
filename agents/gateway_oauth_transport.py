"""
OAuth Bearer Token Transport for MCP Gateway Access

This module provides a custom HTTP transport that uses OAuth Bearer tokens
for accessing AgentCore Gateways with CUSTOM_JWT authorization.
"""

import httpx
from mcp.client.streamable_http import streamablehttp_client
from contextlib import asynccontextmanager
from agents.oauth_token_manager import OAuthTokenManager


@asynccontextmanager
async def gateway_oauth_transport(url: str, token_manager: OAuthTokenManager):
    """
    Create an MCP HTTP transport with OAuth Bearer token authentication.

    This function creates an httpx Auth class that adds Bearer token
    to every request sent to the Gateway.

    Args:
        url: Gateway MCP endpoint URL
        token_manager: OAuth token manager for getting valid tokens

    Yields:
        MCP transport configured with OAuth authentication
    """

    # Create a custom Auth class for httpx that adds Bearer token
    class GatewayOAuthAuth(httpx.Auth):
        """HTTP Auth that adds OAuth Bearer token to requests"""

        def auth_flow(self, request):
            """Add Bearer token to the request and yield it"""

            # Get a valid access token (will refresh if needed)
            access_token = token_manager.get_token()

            print(f"[OAuth] Adding Bearer token to request: {request.url}")
            print(f"[OAuth] Token: {access_token[:20]}...{access_token[-10:]}")

            # Add Authorization header with Bearer token
            request.headers["Authorization"] = f"Bearer {access_token}"

            # Yield the authenticated request
            yield request

    # Use the standard streamable HTTP client with our custom OAuth auth
    async with streamablehttp_client(url, auth=GatewayOAuthAuth()) as transport:
        yield transport
