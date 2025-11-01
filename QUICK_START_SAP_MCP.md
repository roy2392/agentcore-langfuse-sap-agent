# Quick Start: SAP MCP Server

## What's New

The agent now uses a **SAP MCP Server** instead of Langfuse MCP for accessing inventory data. This gives the agent direct access to real SAP data through 8 different tools.

## 1-Minute Setup

### Step 1: Store SAP Credentials
```bash
# Set these to your actual SAP system details
SAP_HOST="your-sap-server.com"
SAP_USER="your_username"
SAP_PASSWORD="your_password"

# Store in AWS SSM (encrypted)
aws ssm put-parameter --name /sap/SAP_HOST --value "$SAP_HOST" --type SecureString --region us-east-1
aws ssm put-parameter --name /sap/SAP_USER --value "$SAP_USER" --type SecureString --region us-east-1
aws ssm put-parameter --name /sap/SAP_PASSWORD --value "$SAP_PASSWORD" --type SecureString --region us-east-1
```

### Step 2: Deploy SAP MCP Server to AWS
```bash
python cicd/deploy_sap_mcp.py --region us-east-1 --deploy-ecs
```

This will:
- Build Docker image
- Push to AWS ECR
- Create ECS task definition
- Save config to `cicd/sap_mcp_config.json`

### Step 3: Deploy Updated Agent
```bash
python cicd/deploy_agent.py --environment TST
```

### Step 4: Generate Evaluation Data (Optional)
```bash
python cicd/generate_sap_evaluation_data.py
```

## Testing Locally

### Test SAP API Connection
```bash
export SAP_HOST="your-sap-host"
export SAP_USER="your_user"
export SAP_PASSWORD="your_password"

# Run this to verify connectivity
python utils/test_sap_api.py
```

### Test MCP Server Directly
```bash
# List available tools
python utils/sap_mcp_server.py --list-tools

# Test a specific tool
python utils/sap_mcp_server.py \
  --test-tool get_stock_levels \
  --input '{"material_number": "100-100"}'
```

### Run Agent Test
```bash
python cicd/tst.py
```

## Available Tools

The agent can use these 8 tools automatically:

| Tool | Purpose | Hebrew Example |
|------|---------|---|
| `get_stock_levels` | Query stock for a material | "כמה יחידות של מוצר 100-100 יש לנו?" |
| `get_low_stock_materials` | Find low stock items | "אילו מוצרים במלאי נמוך?" |
| `get_material_info` | Material details | "מה סוג המוצר 100-100?" |
| `get_warehouse_stock` | Warehouse summary | "מה המצב במחסן 01?" |
| `get_purchase_orders_for_material` | Pending orders | "האם יש הזמנות עבור 100-100?" |
| `get_goods_receipt` | Delivery status | "מה סטטוס ההזמנה 4500000520?" |
| `forecast_material_demand` | Demand forecast | "מה ההיקף של הביקוש לחודש הבא?" |
| `get_complete_po_data` | Full PO details | "מה פרטי הזמנה 4500000520?" |

## Architecture

```
User (Hebrew Query)
    ↓
Agent (Claude 3 Sonnet)
    ↓
SAP MCP Server (Port 8000)
    ↓
SAP OData APIs
    ↓
Agent (Hebrew Response)
```

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SAP_MCP_HOST` | `localhost` | MCP server hostname |
| `SAP_MCP_PORT` | `8000` | MCP server port |
| `SAP_HOST` | (from SSM) | SAP system host |
| `SAP_USER` | (from SSM) | SAP system user |
| `SAP_PASSWORD` | (from SSM) | SAP system password |

### Docker Compose (Optional)
```yaml
services:
  sap-mcp-server:
    image: 123456789.dkr.ecr.us-east-1.amazonaws.com/sap-mcp-server:latest
    environment:
      SAP_HOST: ${SAP_HOST}
      SAP_USER: ${SAP_USER}
      SAP_PASSWORD: ${SAP_PASSWORD}
    ports:
      - "8000:8000"
    healthcheck:
      test: python -c "import os; exit(0 if all([os.getenv('SAP_HOST'), os.getenv('SAP_USER'), os.getenv('SAP_PASSWORD')]) else 1)"
      interval: 30s
      timeout: 10s
      retries: 3

  agent:
    image: 123456789.dkr.ecr.us-east-1.amazonaws.com/strands-agent:latest
    environment:
      SAP_MCP_HOST: sap-mcp-server
      SAP_MCP_PORT: 8000
      BEDROCK_MODEL_ID: anthropic.claude-3-sonnet-20240229-v1:0
    depends_on:
      sap-mcp-server:
        condition: service_healthy
```

## Troubleshooting

### "SAP credentials not found"
```bash
# Verify credentials are in SSM
aws ssm get-parameter --name /sap/SAP_HOST --region us-east-1 --with-decryption
aws ssm get-parameter --name /sap/SAP_USER --region us-east-1 --with-decryption
aws ssm get-parameter --name /sap/SAP_PASSWORD --region us-east-1 --with-decryption
```

### "Connection refused to SAP MCP server"
```bash
# Check if MCP server is running
docker ps | grep sap-mcp-server

# Check logs
docker logs <container-id>

# Test locally
curl -f http://localhost:8000/health
```

### "SAP API authentication failed"
```bash
# Verify SAP connectivity
python utils/test_sap_api.py

# Check SAP_HOST, SAP_USER, SAP_PASSWORD are correct
echo $SAP_HOST
echo $SAP_USER
# (don't echo password!)
```

## Important Changes from Previous Version

| Before | After |
|--------|-------|
| Used Langfuse MCP for tool discovery | Uses SAP MCP Server on port 8000 |
| Hardcoded Langfuse URL | Dynamic SAP MCP connection |
| Langfuse required for agent | Langfuse optional (telemetry only) |
| No direct SAP access | Direct real-time SAP OData access |
| Generic agent | Hebrew-focused inventory agent |

## Next Steps

1. **Configure SAP credentials** in AWS SSM Parameter Store
2. **Deploy SAP MCP Server** to AWS ECR/ECS
3. **Deploy updated agent** to TST environment
4. **Generate evaluation data** from real SAP queries
5. **Run TST evaluation** to verify agent quality
6. **Deploy to PRD** when ready

## Files Changed

**New Files:**
- `utils/sap_mcp_server.py` - MCP server implementation
- `cicd/deploy_sap_mcp.py` - Deployment script
- `cicd/generate_sap_evaluation_data.py` - Evaluation data generator
- `SAP_MCP_DEPLOYMENT.md` - Full documentation
- `SAP_MCP_SUMMARY.md` - Implementation summary

**Modified Files:**
- `agents/strands_claude.py` - Now uses SAP MCP instead of Langfuse MCP
- `Dockerfile.sap-mcp` - Updated with MCP server configuration

## More Information

See:
- **Full Setup Guide**: `SAP_MCP_DEPLOYMENT.md`
- **Implementation Details**: `SAP_MCP_SUMMARY.md`
- **Tool Reference**: `SAP_MCP_DEPLOYMENT.md` → "MCP Tools Reference"

## Support

For issues, see the **Troubleshooting** section in `SAP_MCP_DEPLOYMENT.md` or review the MCP server logs:

```bash
# View MCP server logs
docker logs <sap-mcp-server-container-id> -f

# View agent logs
docker logs <agent-container-id> -f
```

---

**Key Point**: The agent now has direct access to real SAP inventory data through the MCP server, providing accurate, up-to-date responses to Hebrew-language inventory queries.
