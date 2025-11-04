#!/usr/bin/env python3
"""
Test script to verify tool availability in agent directly
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set minimal environment
os.environ['GATEWAY_ENDPOINT_URL'] = 'https://sap-inventory-gateway-prd-td3ict6das.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp'
os.environ['COGNITO_CLIENT_ID'] = '56d6r0as0inbf6gvjjfrmp0c9v'
os.environ['COGNITO_DOMAIN'] = 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_7m45pE9la'

# Set Cognito secret from environment if available
if 'COGNITO_CLIENT_SECRET' in os.environ:
    print(f"✅ COGNITO_CLIENT_SECRET is set")
else:
    print(f"❌ COGNITO_CLIENT_SECRET is NOT set - OAuth won't work!")
    print("Set it with: export COGNITO_CLIENT_SECRET=<secret>")
    sys.exit(1)

print("Testing tool availability...")
print(f"Gateway URL: {os.environ['GATEWAY_ENDPOINT_URL']}")
print()

# Import MCP client setup from agent
try:
    from strands.tools.mcp.mcp_client import MCPClient
    from agents.gateway_oauth_transport import gateway_oauth_transport
    from agents.oauth_token_manager import create_token_manager_from_env

    print("✅ Imported MCP client and OAuth transport")

    # Create OAuth token manager
    token_manager = create_token_manager_from_env()

    if not token_manager:
        print("❌ Failed to create OAuth token manager")
        sys.exit(1)

    print("✅ Created OAuth token manager")

    # Create MCP client
    def create_transport():
        return gateway_oauth_transport(os.environ['GATEWAY_ENDPOINT_URL'], token_manager)

    mcp_client = MCPClient(create_transport)
    print("✅ Created MCP client")
    print()

    # Try to list tools
    print("Attempting to list tools from Gateway...")
    try:
        # The MCPClient should be able to list tools
        print("Note: MCPClient doesn't expose a list_tools method directly")
        print("Tools are loaded dynamically when the agent runs")
        print()

        # Try to get tool schema
        print("MCPClient attributes:", dir(mcp_client))
        print()

    except Exception as e:
        print(f"❌ Error listing tools: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
