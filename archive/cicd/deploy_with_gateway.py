#!/usr/bin/env python3
"""
Deploy SAP Agent with AgentCore Gateway Architecture

This script deploys the complete AgentCore Gateway architecture:
1. SAP MCP Server (containerized)
2. AgentCore Gateway with MCP target
3. AgentCore Identity for SAP credentials
4. Agent Runtime with Gateway endpoint

Follows AWS best practices:
- Agent accesses tools through Gateway (not direct API calls)
- Credentials managed by AgentCore Identity (not in agent code)
- Gateway handles OAuth authentication
- Stateless, scalable architecture
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from utils.gateway import deploy_sap_gateway
from utils.agent import deploy_agent


def deploy_complete_architecture(environment="PRD"):
    """
    Deploy complete SAP agent architecture with Gateway

    Steps:
    1. Build and deploy SAP MCP Server container
    2. Create AgentCore Gateway
    3. Configure Gateway MCP target pointing to SAP MCP Server
    4. Store SAP credentials in AgentCore Identity
    5. Deploy agent with Gateway endpoint URL

    Args:
        environment: Deployment environment (PRD, TST, DEV)
    """

    print("\n" + "="*80)
    print("DEPLOYING SAP AGENT WITH AGENTCORE GATEWAY ARCHITECTURE")
    print("="*80 + "\n")

    # Get SAP credentials from environment
    sap_host = os.getenv('SAP_HOST')
    sap_user = os.getenv('SAP_USER')
    sap_password = os.getenv('SAP_PASSWORD')

    if not all([sap_host, sap_user, sap_password]):
        print("❌ ERROR: SAP credentials not found in environment")
        print("   Set: SAP_HOST, SAP_USER, SAP_PASSWORD")
        return None

    # Step 1: Deploy SAP MCP Server (Docker container)
    print("Step 1: SAP MCP Server Deployment")
    print("-" * 80)
    print("TODO: Deploy SAP MCP Server container to ECS/EKS/Fargate")
    print("  Image: Built from Dockerfile.sap-mcp")
    print("  Port: 8000/mcp")
    print("  Env vars: SAP_HOST, SAP_USER, SAP_PASSWORD")
    print("\nFor now, assuming MCP server is deployed at:")

    # TODO: Replace with actual deployed MCP server URL
    # This could be:
    # - ECS service URL
    # - Load balancer URL
    # - VPC endpoint
    mcp_server_url = os.getenv('SAP_MCP_SERVER_URL', 'http://sap-mcp-server.internal:8000/mcp')
    print(f"  MCP Server URL: {mcp_server_url}")

    # Step 2: Deploy AgentCore Gateway
    print("\nStep 2: AgentCore Gateway Deployment")
    print("-" * 80)

    sap_credentials = {
        'SAP_HOST': sap_host,
        'SAP_USER': sap_user,
        'SAP_PASSWORD': sap_password
    }

    try:
        gateway_result = deploy_sap_gateway(
            gateway_name=f"sap-inventory-gateway-{environment.lower()}",
            mcp_server_url=mcp_server_url,
            sap_credentials=sap_credentials,
            region=os.getenv('AWS_REGION', 'us-east-1')
        )

        gateway_endpoint = gateway_result['gateway_endpoint']

    except Exception as e:
        print(f"\n❌ Gateway deployment failed: {e}")
        print("\nNote: AgentCore Gateway APIs may not be fully available yet")
        print("      This is preview functionality - check AWS documentation")
        return None

    # Step 3: Deploy Agent with Gateway endpoint
    print("\nStep 3: Agent Runtime Deployment")
    print("-" * 80)

    # Set Gateway endpoint in environment for agent deployment
    os.environ['GATEWAY_ENDPOINT_URL'] = gateway_endpoint

    # Model configuration
    model = {
        "name": "sonnet",
        "model_id": "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
    }

    # System prompt (Hebrew inventory management)
    system_prompt = {
        "name": "inventory",
        "prompt": "אתה סוכן מומחה בניהול מלאי. התשובות שלך צריכות להיות בעברית בלבד."
    }

    try:
        agent_result = deploy_agent(
            model=model,
            system_prompt=system_prompt,
            force_redeploy=False,
            environment=environment
        )

        print("\n" + "="*80)
        print("✓ COMPLETE DEPLOYMENT SUCCESSFUL")
        print("="*80)
        print(f"\nArchitecture:")
        print(f"  Agent Runtime → Gateway → MCP Target → SAP MCP Server → SAP API")
        print(f"\nComponents:")
        print(f"  1. SAP MCP Server: {mcp_server_url}")
        print(f"  2. Gateway Endpoint: {gateway_endpoint}")
        print(f"  3. Agent: {agent_result['agent_name']}")
        print(f"     ARN: {agent_result['launch_result'].agent_arn}")
        print(f"\nCredentials:")
        print(f"  Managed by AgentCore Identity (NOT in agent code)")
        print(f"  SAP Host: {sap_host}")
        print(f"\nNext Steps:")
        print(f"  1. Test agent: python -m utils.agent invoke <agent-arn> '<question>'")
        print(f"  2. Run evaluations: python cicd/evaluate_with_sap_mcp.py --agent-name {agent_result['agent_name']}")
        print(f"  3. Check Langfuse: {os.getenv('LANGFUSE_HOST')}")

        return {
            'mcp_server_url': mcp_server_url,
            'gateway': gateway_result,
            'agent': agent_result
        }

    except Exception as e:
        print(f"\n❌ Agent deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy SAP Agent with Gateway")
    parser.add_argument('--environment', default='PRD', choices=['PRD', 'TST', 'DEV'],
                       help='Deployment environment')
    args = parser.parse_args()

    result = deploy_complete_architecture(environment=args.environment)

    if result:
        print("\n✓ Deployment complete!")
        sys.exit(0)
    else:
        print("\n❌ Deployment failed")
        sys.exit(1)
