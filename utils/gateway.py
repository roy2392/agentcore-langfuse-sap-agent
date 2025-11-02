#!/usr/bin/env python3
"""
AWS Bedrock AgentCore Gateway Management

This module handles Gateway creation, target configuration, and Identity setup
following AWS AgentCore best practices.

Architecture:
  Agent → Gateway (OAuth auth) → MCP Target → SAP MCP Server → SAP API

Identity:
  SAP credentials stored in AgentCore Identity (not in agent code)
"""

import boto3
import json
import os
from typing import Dict, Any, Optional

class AgentCoreGateway:
    """Manage AgentCore Gateway for SAP MCP Server integration"""

    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.client = boto3.client('bedrock-agentcore-control', region_name=region)

    def create_gateway(self, gateway_name: str, description: str = None) -> Dict[str, Any]:
        """
        Create an AgentCore Gateway

        Args:
            gateway_name: Name for the gateway
            description: Optional description

        Returns:
            Gateway details including gateway ID and ARN
        """
        params = {
            'name': gateway_name,
        }

        if description:
            params['description'] = description

        try:
            response = self.client.create_gateway(**params)
            print(f"✓ Created Gateway: {gateway_name}")
            print(f"  Gateway ID: {response['gatewayId']}")
            print(f"  Gateway ARN: {response['gatewayArn']}")
            return response
        except Exception as e:
            print(f"❌ Failed to create gateway: {e}")
            raise

    def create_mcp_target(
        self,
        gateway_id: str,
        target_name: str,
        mcp_server_url: str,
        description: str = None
    ) -> Dict[str, Any]:
        """
        Create an MCP Target for the Gateway

        Args:
            gateway_id: Gateway ID to attach target to
            target_name: Name for the target
            mcp_server_url: URL of the MCP server (e.g., http://sap-mcp-server:8000/mcp)
            description: Optional description

        Returns:
            Target details including target ID
        """
        params = {
            'gatewayIdentifier': gateway_id,
            'name': target_name,
            'mcpTargetConfiguration': {
                'serverUrl': mcp_server_url,
                'protocol': 'MCP'
            }
        }

        if description:
            params['description'] = description

        try:
            response = self.client.create_gateway_target(**params)
            print(f"✓ Created MCP Target: {target_name}")
            print(f"  Target ID: {response['targetId']}")
            print(f"  MCP Server URL: {mcp_server_url}")
            return response
        except Exception as e:
            print(f"❌ Failed to create MCP target: {e}")
            raise

    def get_gateway_endpoint(self, gateway_id: str) -> str:
        """
        Get the Gateway endpoint URL

        Args:
            gateway_id: Gateway ID

        Returns:
            Gateway endpoint URL
        """
        try:
            response = self.client.get_gateway(gatewayIdentifier=gateway_id)
            endpoint = response.get('gatewayEndpoint', '')
            print(f"✓ Gateway Endpoint: {endpoint}")
            return endpoint
        except Exception as e:
            print(f"❌ Failed to get gateway endpoint: {e}")
            raise

    def list_gateways(self) -> list:
        """List all gateways"""
        try:
            response = self.client.list_gateways()
            gateways = response.get('gateways', [])
            return gateways
        except Exception as e:
            print(f"❌ Failed to list gateways: {e}")
            raise

    def delete_gateway(self, gateway_id: str):
        """Delete a gateway"""
        try:
            self.client.delete_gateway(gatewayIdentifier=gateway_id)
            print(f"✓ Deleted Gateway: {gateway_id}")
        except Exception as e:
            print(f"❌ Failed to delete gateway: {e}")
            raise


class AgentCoreIdentity:
    """Manage AgentCore Identity for credential storage"""

    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.client = boto3.client('bedrock-agentcore-identity', region_name=region)

    def create_credential_provider(
        self,
        provider_name: str,
        sap_host: str,
        sap_user: str,
        sap_password: str
    ) -> Dict[str, Any]:
        """
        Create a credential provider for SAP API access

        Args:
            provider_name: Name for the credential provider
            sap_host: SAP host URL
            sap_user: SAP username
            sap_password: SAP password

        Returns:
            Credential provider details
        """
        # Note: This is a placeholder - actual implementation depends on
        # AgentCore Identity API which may use Secrets Manager
        try:
            # Store credentials in AWS Secrets Manager
            secrets_client = boto3.client('secretsmanager', region_name=self.region)

            secret_name = f"agentcore/sap/{provider_name}"
            secret_value = {
                'SAP_HOST': sap_host,
                'SAP_USER': sap_user,
                'SAP_PASSWORD': sap_password
            }

            response = secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description=f'SAP credentials for AgentCore Gateway target: {provider_name}'
            )

            print(f"✓ Created credential provider: {provider_name}")
            print(f"  Secret ARN: {response['ARN']}")

            return {
                'secretName': secret_name,
                'secretArn': response['ARN']
            }
        except Exception as e:
            print(f"❌ Failed to create credential provider: {e}")
            raise


def deploy_sap_gateway(
    gateway_name: str = "sap-inventory-gateway",
    mcp_server_url: str = None,
    sap_credentials: Dict[str, str] = None,
    region: str = 'us-east-1'
) -> Dict[str, Any]:
    """
    Deploy complete SAP Gateway infrastructure

    Args:
        gateway_name: Name for the gateway
        mcp_server_url: URL of deployed SAP MCP server
        sap_credentials: Dict with SAP_HOST, SAP_USER, SAP_PASSWORD
        region: AWS region

    Returns:
        Deployment details including gateway endpoint
    """
    print("\n" + "="*80)
    print("DEPLOYING SAP AGENTCORE GATEWAY")
    print("="*80 + "\n")

    # Initialize managers
    gateway_mgr = AgentCoreGateway(region=region)
    identity_mgr = AgentCoreIdentity(region=region)

    # Step 1: Create Gateway
    print("Step 1: Creating Gateway...")
    gateway_result = gateway_mgr.create_gateway(
        gateway_name=gateway_name,
        description="Gateway for SAP inventory management via MCP"
    )
    gateway_id = gateway_result['gatewayId']

    # Step 2: Create Credential Provider (if credentials provided)
    if sap_credentials:
        print("\nStep 2: Creating SAP Credential Provider...")
        credential_result = identity_mgr.create_credential_provider(
            provider_name=f"{gateway_name}-credentials",
            sap_host=sap_credentials['SAP_HOST'],
            sap_user=sap_credentials['SAP_USER'],
            sap_password=sap_credentials['SAP_PASSWORD']
        )

    # Step 3: Create MCP Target
    if mcp_server_url:
        print("\nStep 3: Creating MCP Target...")
        target_result = gateway_mgr.create_mcp_target(
            gateway_id=gateway_id,
            target_name="sap-mcp-target",
            mcp_server_url=mcp_server_url,
            description="SAP OData API via MCP Server"
        )

    # Step 4: Get Gateway Endpoint
    print("\nStep 4: Getting Gateway Endpoint...")
    gateway_endpoint = gateway_mgr.get_gateway_endpoint(gateway_id)

    print("\n" + "="*80)
    print("✓ DEPLOYMENT COMPLETE")
    print("="*80)
    print(f"\nGateway Endpoint (use in agent): {gateway_endpoint}")
    print(f"Set environment variable: GATEWAY_ENDPOINT_URL={gateway_endpoint}")

    return {
        'gateway_id': gateway_id,
        'gateway_endpoint': gateway_endpoint,
        'gateway_arn': gateway_result['gatewayArn']
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy SAP AgentCore Gateway")
    parser.add_argument('--gateway-name', default='sap-inventory-gateway', help='Gateway name')
    parser.add_argument('--mcp-url', required=True, help='SAP MCP Server URL')
    parser.add_argument('--region', default='us-east-1', help='AWS region')

    args = parser.parse_args()

    # Get SAP credentials from environment
    sap_creds = None
    if all([os.getenv('SAP_HOST'), os.getenv('SAP_USER'), os.getenv('SAP_PASSWORD')]):
        sap_creds = {
            'SAP_HOST': os.getenv('SAP_HOST'),
            'SAP_USER': os.getenv('SAP_USER'),
            'SAP_PASSWORD': os.getenv('SAP_PASSWORD')
        }

    result = deploy_sap_gateway(
        gateway_name=args.gateway_name,
        mcp_server_url=args.mcp_url,
        sap_credentials=sap_creds,
        region=args.region
    )

    print(f"\n✓ Gateway deployed successfully!")
    print(f"  Gateway ID: {result['gateway_id']}")
    print(f"  Endpoint: {result['gateway_endpoint']}")
