"""
AWS SigV4 Transport for MCP Gateway Access

This module provides a custom HTTP transport that signs all requests with AWS SigV4
for accessing IAM-protected AgentCore Gateways.
"""

import httpx
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from mcp.client.streamable_http import streamablehttp_client
from contextlib import asynccontextmanager


@asynccontextmanager
async def gateway_sigv4_transport(url: str, region: str = "us-east-1"):
    """
    Create an MCP HTTP transport with AWS SigV4 signing.

    This function creates an httpx Auth class that signs every request
    with AWS SigV4 before sending it to the Gateway.
    """
    # Get AWS session (credentials will be refreshed per-request)
    session = boto3.Session()

    # Create a custom Auth class for httpx that signs requests
    class GatewaySigV4Auth(httpx.Auth):
        """HTTP Auth that signs requests with AWS SigV4"""

        def auth_flow(self, request):
            """Sign the request with SigV4 and yield it"""
            # Get fresh credentials for this request
            credentials = session.get_credentials()

            if not credentials:
                raise ValueError("No AWS credentials available. Agent's IAM role may not be configured correctly.")

            print(f"[SigV4] Signing request to: {request.url}")
            print(f"[SigV4] Method: {request.method}")
            print(f"[SigV4] Credentials: AccessKey={credentials.access_key[:10]}... (role credentials)")

            # Create an AWS request object for signing
            aws_request = AWSRequest(
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers),
                data=request.content if request.content else b''
            )

            # Sign the request
            signer = SigV4Auth(credentials, "bedrock-agentcore", region)
            signer.add_auth(aws_request)

            print(f"[SigV4] Authorization header: {aws_request.headers.get('Authorization', 'MISSING')[:80]}...")

            # Copy signed headers back to the httpx request
            for key, value in aws_request.headers.items():
                request.headers[key] = value

            # Yield the signed request
            yield request

    # Use the standard streamable HTTP client with our custom auth
    async with streamablehttp_client(url, auth=GatewaySigV4Auth()) as transport:
        yield transport
