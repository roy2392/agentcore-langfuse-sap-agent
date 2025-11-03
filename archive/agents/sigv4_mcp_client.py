"""
AWS SigV4 Signed MCP HTTP Client

This module provides an MCP client that automatically signs requests with AWS SigV4
for accessing IAM-protected AgentCore Gateways.
"""

import httpx
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from mcp.client.streamable_http import streamablehttp_client
from typing import AsyncIterator
from contextlib import asynccontextmanager


class SigV4HTTPTransport:
    """HTTP transport that signs requests with AWS SigV4"""

    def __init__(self, url: str, region: str = "us-east-1"):
        self.url = url
        self.region = region
        self.session = boto3.Session()
        self.credentials = self.session.get_credentials()

    def sign_request(self, method: str, url: str, headers: dict, body: bytes) -> dict:
        """Sign an HTTP request with AWS SigV4"""
        request = AWSRequest(method=method, url=url, headers=headers, data=body)
        SigV4Auth(self.credentials, "bedrock-agentcore", self.region).add_auth(request)
        return dict(request.headers)


@asynccontextmanager
async def sigv4_streamablehttp_client(url: str, region: str = "us-east-1"):
    """
    Create an MCP streamable HTTP client with AWS SigV4 signing

    This wraps the standard streamablehttp_client and adds SigV4 signing
    to all outgoing requests.
    """
    # Get AWS credentials
    session = boto3.Session()
    credentials = session.get_credentials()

    # Create httpx client with auth
    from httpx import Auth, Request, Response

    class SigV4Auth(Auth):
        def auth_flow(self, request: Request) -> AsyncIterator[Request]:
            # Sign the request
            aws_request = AWSRequest(
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers),
                data=request.content
            )

            from botocore.auth import SigV4Auth as BotoSigV4Auth
            signer = BotoSigV4Auth(credentials, "bedrock-agentcore", region)
            signer.add_auth(aws_request)

            # Update request headers
            for key, value in aws_request.headers.items():
                request.headers[key] = value

            yield request

    # Use the standard streamablehttp_client with auth
    async with streamablehttp_client(url, auth=SigV4Auth()) as transport_tuple:
        yield transport_tuple
