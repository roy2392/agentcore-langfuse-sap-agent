# AWS AgentCore Gateway Architecture

## Overview

This project follows **AWS Bedrock AgentCore best practices** with proper Gateway and Identity management.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      USER REQUEST                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               BEDROCK AGENTCORE RUNTIME                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Strands Agent (agents/strands_claude.py)            │  │
│  │  - NO direct SAP API calls                           │  │
│  │  - NO embedded credentials                           │  │
│  │  - Uses Gateway endpoint for tools                   │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          │ GATEWAY_ENDPOINT_URL
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENTCORE GATEWAY                               │
│                                                              │
│  - OAuth Authentication (Inbound)                           │
│  - IAM Authorization                                        │
│  - Credential Injection (Outbound)                          │
│  - Tool Discovery & Routing                                 │
│                                                              │
│  Gateway ID: sap-inventory-gateway-prd                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ MCP Target
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               SAP MCP SERVER                                 │
│                                                              │
│  Container: Dockerfile.sap-mcp                              │
│  Endpoint: http://sap-mcp-server:8000/mcp                   │
│  Protocol: Streamable-HTTP MCP                              │
│                                                              │
│  Tools Exposed:                                             │
│    - get_stock_levels                                       │
│    - get_low_stock_materials                                │
│    - get_material_info                                      │
│    - get_warehouse_stock                                    │
│    - get_purchase_orders                                    │
│    - get_goods_receipt                                      │
│    - forecast_demand                                        │
│    - get_complete_po_data                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ SAP Credentials (from Identity)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 SAP ODATA API                                │
│                                                              │
│  Host: aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev  │
│  User: AWSDEMO                                              │
│  Services:                                                  │
│    - Purchase Order API (Working)                           │
│    - Material Stock API (403 - Limited permissions)         │
│    - Goods Receipt API (403 - Limited permissions)          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           AGENTCORE IDENTITY (Credential Storage)            │
│                                                              │
│  - Stores SAP_HOST, SAP_USER, SAP_PASSWORD                  │
│  - Credentials injected at Gateway target level             │
│  - NOT embedded in agent code                               │
│  - Managed via AWS Secrets Manager                          │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Agent Runtime (`agents/strands_claude.py`)
- **Responsibility**: Process user requests, orchestrate tool calls
- **Tools Source**: AgentCore Gateway (NOT embedded)
- **Credentials**: NONE (uses Gateway)
- **Environment Variables**:
  - `GATEWAY_ENDPOINT_URL` - Gateway endpoint for tool access
  - `BEDROCK_MODEL_ID` - Claude model to use
  - `LANGFUSE_*` - Tracing configuration

### 2. AgentCore Gateway
- **Responsibility**: Tool discovery, authentication, routing
- **Inbound Auth**: OAuth (validates agent requests)
- **Outbound Auth**: IAM + Credential Injection
- **Targets**: MCP Target → SAP MCP Server

### 3. SAP MCP Server (`Dockerfile.sap-mcp`)
- **Responsibility**: Expose SAP APIs as MCP tools
- **Protocol**: Streamable-HTTP MCP
- **Endpoint**: `POST /mcp` (tools/list, tools/call)
- **Session**: Supports `Mcp-Session-Id` header
- **Deployment**: ECS/Fargate/EKS container

### 4. AgentCore Identity
- **Responsibility**: Credential storage and management
- **Storage**: AWS Secrets Manager
- **Injection**: Gateway injects credentials to MCP server
- **Credentials**: SAP_HOST, SAP_USER, SAP_PASSWORD

## Deployment

### Prerequisites
```bash
# Set environment variables
export AWS_REGION=us-east-1
export SAP_HOST=aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev
export SAP_USER=AWSDEMO
export SAP_PASSWORD=<password>
export LANGFUSE_SECRET_KEY=<key>
export LANGFUSE_PUBLIC_KEY=<key>
export LANGFUSE_HOST=https://cloud.langfuse.com
```

### Step 1: Deploy SAP MCP Server
```bash
# Build Docker image
docker build -f Dockerfile.sap-mcp -t sap-mcp-server:latest .

# Deploy to ECS/Fargate (example)
# TODO: Add actual ECS deployment commands
# The container must be accessible at a URL the Gateway can reach

# Example service URL:
# http://sap-mcp-server.internal:8000/mcp
```

### Step 2: Deploy Gateway
```bash
# Deploy Gateway with MCP target
python -m utils.gateway \
  --gateway-name sap-inventory-gateway \
  --mcp-url http://sap-mcp-server.internal:8000/mcp \
  --region us-east-1

# Output will include:
# Gateway Endpoint: https://<gateway-id>.agentcore.us-east-1.amazonaws.com
```

### Step 3: Deploy Agent
```bash
# Set Gateway endpoint
export GATEWAY_ENDPOINT_URL=https://<gateway-id>.agentcore.us-east-1.amazonaws.com

# Deploy agent
python cicd/deploy_with_gateway.py --environment PRD
```

### Complete Deployment (All Steps)
```bash
# Run complete deployment script
python cicd/deploy_with_gateway.py --environment PRD
```

## Testing

### Test SAP MCP Server Directly
```bash
# Start MCP server locally
python utils/sap_mcp_http_server.py --port 8000

# Test tools list
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list"}'

# Test tool execution
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_complete_po_data",
      "arguments": {"po_number": "4500000520"}
    }
  }'
```

### Test Agent with Gateway
```bash
# Run evaluation with deployed agent
python cicd/evaluate_with_sap_mcp.py \
  --agent-name strands_sonnet_inventory_PRD

# Traces will appear in Langfuse
```

## Security & Best Practices

### ✅ What We Follow
- **Gateway Pattern**: Agent → Gateway → MCP → API (no direct API access)
- **Identity Management**: Credentials in AgentCore Identity, NOT in code
- **OAuth Auth**: Gateway enforces authentication
- **Stateless Protocol**: MCP server uses streamable-HTTP
- **Session Continuity**: `Mcp-Session-Id` header support
- **Credential Injection**: Gateway injects credentials at target level

### ❌ What We Avoid
- ❌ Embedding API credentials in agent code
- ❌ Direct API calls from agent
- ❌ Stateful MCP connections
- ❌ Hardcoded endpoints
- ❌ Mixed authentication patterns

## File Structure

```
agentcore-langfuse-sap-agent/
├── agents/
│   └── strands_claude.py        # Agent (uses Gateway, no direct SAP calls)
├── utils/
│   ├── sap_mcp_server.py        # MCP server core logic
│   ├── sap_mcp_http_server.py   # Streamable-HTTP wrapper (Gateway compatible)
│   ├── gateway.py               # Gateway & Identity management
│   └── agent.py                 # Agent deployment
├── cicd/
│   ├── deploy_with_gateway.py   # Complete deployment script
│   └── evaluate_with_sap_mcp.py # Evaluation with agent invocation
├── Dockerfile.sap-mcp           # SAP MCP Server container
└── ARCHITECTURE.md              # This file
```

## Migration from Old Architecture

### Old (Direct API Access)
```python
# ❌ OLD - Direct SAP API calls in agent
from utils.test_sap_api import get_stock_levels

@tool
def sap_get_stock_levels(material: str):
    return get_stock_levels(material)

agent = Agent(tools=[sap_get_stock_levels])
```

### New (Gateway Pattern)
```python
# ✅ NEW - Tools via Gateway
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

gateway_url = os.getenv("GATEWAY_ENDPOINT_URL")
mcp_client = MCPClient(lambda: streamablehttp_client(gateway_url))

agent = Agent(tools=[mcp_client])  # Tools from Gateway
```

## Troubleshooting

### Agent has no tools
- Check `GATEWAY_ENDPOINT_URL` is set
- Verify Gateway is deployed and accessible
- Check Gateway has MCP target configured

### 403 Forbidden from SAP API
- AWSDEMO user has limited permissions
- Only Purchase Order APIs work
- Stock/Material APIs require additional SAP permissions

### MCP server not responding
- Check container is running
- Verify endpoint is `POST /mcp` (not `/mcp/tools`)
- Check `Mcp-Session-Id` header is supported

### Gateway not found
- AgentCore Gateway APIs are preview functionality
- Check region availability
- Verify AWS credentials have correct permissions

## References

- [AWS AgentCore Gateway Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [AgentCore Identity](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-identity-securing-agentic-ai-at-scale/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Streamable-HTTP MCP](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)
