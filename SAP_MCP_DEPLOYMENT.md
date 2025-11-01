# SAP MCP Server Deployment Guide

This guide explains how to deploy and use the SAP Model Context Protocol (MCP) Server as part of the Bedrock AgentCore inventory management agent.

## Overview

The SAP MCP Server exposes SAP OData APIs as tools that can be called by the Bedrock AgentCore agent. This allows the agent to query real-time inventory data, purchase orders, and material information directly from your SAP system.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Bedrock AgentCore Agent (Hebrew)                │
│  (strands_claude.py - Claude 3 Sonnet)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ Uses MCP Tools
                       ▼
┌──────────────────────────────────────────────────────────┐
│          SAP MCP Server                                  │
│  (sap_mcp_server.py - Port 8000)                         │
│                                                          │
│  Available Tools:                                        │
│  ├─ get_stock_levels                                    │
│  ├─ get_low_stock_materials                             │
│  ├─ get_material_info                                   │
│  ├─ get_warehouse_stock                                 │
│  ├─ get_purchase_orders_for_material                    │
│  ├─ get_goods_receipt                                   │
│  ├─ forecast_material_demand                            │
│  └─ get_complete_po_data                                │
└──────────────────────┬──────────────────────────────────┘
                       │ REST Calls
                       ▼
┌──────────────────────────────────────────────────────────┐
│           SAP OData API                                  │
│  (test_sap_api.py - urllib client)                       │
│                                                          │
│  Services:                                               │
│  ├─ C_MATERIAL_STOCK_SRV                                │
│  ├─ C_PURCHASEORDER_FS_SRV                              │
│  ├─ C_MATERIAL_SRV                                      │
│  ├─ C_GOODSRECEIPT_SRV                                  │
│  └─ C_DEMANDFORECAST_SRV                                │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS (Basic Auth)
                       ▼
┌──────────────────────────────────────────────────────────┐
│              SAP System                                  │
│   (Backend ERP with OData Endpoints)                     │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- AWS CLI configured with credentials
- AWS ECR access for image repository
- SAP system with OData API enabled
- SAP credentials: Host, User, Password

## File Structure

```
agentcore-langfuse-sap-agent/
├── agents/
│   └── strands_claude.py          # Main agent (updated to use SAP MCP)
├── utils/
│   ├── test_sap_api.py            # SAP OData API client
│   ├── sap_mcp_server.py          # MCP server implementation
│   └── agent.py, langfuse.py, aws.py
├── cicd/
│   ├── deploy_sap_mcp.py          # Deployment script
│   └── generate_sap_evaluation_data.py  # Evaluation data generator
├── Dockerfile                      # Main agent Dockerfile
├── Dockerfile.sap-mcp             # SAP MCP Server Dockerfile
└── docker-compose.yml             # Local development (if available)
```

## Setup Instructions

### 1. Configure SAP Credentials

Store SAP credentials in AWS SSM Parameter Store:

```bash
# Set your SAP system details
export SAP_HOST="your-sap-host.example.com"
export SAP_USER="your_sap_user"
export SAP_PASSWORD="your_sap_password"

# Store in SSM (us-east-1 region)
aws ssm put-parameter \
  --name "/sap/SAP_HOST" \
  --value "$SAP_HOST" \
  --type "SecureString" \
  --region us-east-1

aws ssm put-parameter \
  --name "/sap/SAP_USER" \
  --value "$SAP_USER" \
  --type "SecureString" \
  --region us-east-1

aws ssm put-parameter \
  --name "/sap/SAP_PASSWORD" \
  --value "$SAP_PASSWORD" \
  --type "SecureString" \
  --region us-east-1
```

### 2. Local Testing

Test the SAP API client locally:

```bash
# Set environment variables
export SAP_HOST="your-sap-host"
export SAP_USER="your_user"
export SAP_PASSWORD="your_password"

# Test SAP API directly
python utils/test_sap_api.py

# Test MCP Server
python utils/sap_mcp_server.py --list-tools
python utils/sap_mcp_server.py --test-tool get_stock_levels --input '{"material_number": "100-100"}'
```

### 3. Build and Push to ECR

```bash
# Deploy SAP MCP Server to ECR
python cicd/deploy_sap_mcp.py \
  --region us-east-1 \
  --tag latest

# With ECS deployment
python cicd/deploy_sap_mcp.py \
  --region us-east-1 \
  --tag latest \
  --deploy-ecs \
  --task-family sap-mcp-server
```

### 4. Generate Evaluation Data

Generate static evaluation data by querying actual SAP data:

```bash
export SAP_HOST="your-sap-host"
export SAP_USER="your_user"
export SAP_PASSWORD="your_password"

python cicd/generate_sap_evaluation_data.py
```

This creates:
- `sap_evaluation_data.json` - Evaluation test cases with SAP responses
- Updates Langfuse dataset: `strands-ai-mcp-agent-evaluation`

## MCP Tools Reference

### 1. get_stock_levels
Get current inventory levels for a specific material.

**Input:**
```json
{
  "material_number": "100-100"
}
```

**Output:**
```json
{
  "status": "success",
  "data": {
    "entries": [
      {
        "Material": "100-100",
        "Plant": "1000",
        "StorageLocation": "01",
        "AvailableQuantity": 150,
        "QuantityOnHand": 175,
        "QuantityOrdered": 25,
        "MaterialDescription": "Sample Material"
      }
    ]
  }
}
```

**Hebrew Example:**
```
User: "מה כמות המלאי של המוצר 100-100?"
Agent: "כמות המלאי של המוצר 100-100 היא 150 יחידות זמינות, עם 175 ביד ו-25 מוזמנות"
```

### 2. get_low_stock_materials
Identify materials with stock below threshold.

**Input:**
```json
{
  "threshold": 50
}
```

**Output:** Array of materials with low inventory

**Hebrew Example:**
```
User: "אילו מוצרים יש לנו במלאי נמוך?"
Agent: "מוצרים במלאי נמוך: מוצר A (כמות: 25), מוצר B (כמות: 30)..."
```

### 3. get_material_info
Get detailed information about a material.

**Input:**
```json
{
  "material_number": "100-100"
}
```

**Output:** Material details (description, type, unit of measure, etc.)

### 4. get_warehouse_stock
Get inventory summary for a warehouse/storage location.

**Input:**
```json
{
  "plant": "1000",
  "storage_location": "01"
}
```

**Output:** Aggregated stock statistics for the warehouse

**Hebrew Example:**
```
User: "מה המצב הכללי של המלאי במחסן 01?"
Agent: "סה\"כ 1,250 יחידות זמינות במחסן 01"
```

### 5. get_purchase_orders_for_material
Get pending purchase orders for a material.

**Input:**
```json
{
  "material_number": "100-100"
}
```

**Output:** List of active purchase orders with delivery dates

**Hebrew Example:**
```
User: "כמה מוצרים יישלחו בשבוע הקרוב?"
Agent: "יש הזמנה של 500 יחידות עם תאריך משלוח ב-5.11.2024"
```

### 6. get_goods_receipt
Track goods receipt status for a purchase order.

**Input:**
```json
{
  "po_number": "4500000520"
}
```

**Output:** Receipt details and quantities

### 7. forecast_material_demand
Get demand forecast for material planning.

**Input:**
```json
{
  "material_number": "100-100",
  "days_ahead": 30
}
```

**Output:** Forecasted demand for next 30 days

### 8. get_complete_po_data
Get full purchase order including header and line items.

**Input:**
```json
{
  "po_number": "4500000520"
}
```

**Output:** Complete PO details with items breakdown

**Hebrew Example:**
```
User: "מה סטטוס ההזמנה מסדר קנייה 4500000520?"
Agent: "הזמנה 4500000520: ספק ABC, 3 פריטים, סה\"כ ערך 5,000 ILS..."
```

## Docker Deployment

### Local Docker

```bash
# Build SAP MCP Server image
docker build -f Dockerfile.sap-mcp \
  -t sap-mcp-server:latest .

# Run locally
docker run -d \
  --name sap-mcp-server \
  -e SAP_HOST="your-host" \
  -e SAP_USER="your-user" \
  -e SAP_PASSWORD="your-password" \
  -p 8000:8000 \
  sap-mcp-server:latest

# Test health
curl -f http://localhost:8000/health
```

### AWS ECR

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag sap-mcp-server:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/sap-mcp-server:latest

docker push \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/sap-mcp-server:latest
```

### ECS/Fargate Deployment

The deployment script creates an ECS task definition automatically:

```bash
python cicd/deploy_sap_mcp.py \
  --region us-east-1 \
  --deploy-ecs \
  --task-family sap-mcp-server
```

Configuration saved to: `cicd/sap_mcp_config.json`

## Agent Configuration

The agent automatically connects to the SAP MCP server via environment variables:

```bash
# In deployment (docker-compose or ECS):
SAP_MCP_HOST=sap-mcp-server  # Service name or IP
SAP_MCP_PORT=8000            # Container port
```

The agent code (strands_claude.py) will:
1. Connect to SAP MCP server at `http://{SAP_MCP_HOST}:{SAP_MCP_PORT}/mcp`
2. Load all available tools dynamically
3. Call tools during agent reasoning based on user queries

## Evaluation Dataset

Static evaluation data is generated from actual SAP queries:

```bash
python cicd/generate_sap_evaluation_data.py
```

This creates test cases for:
- Stock level queries
- Low stock reports
- Purchase order status
- Warehouse summaries
- Upcoming deliveries

The data is static and won't change between evaluation runs.

## Troubleshooting

### SAP Credentials Not Set
```
Error: Missing SAP credentials: SAP_HOST, SAP_USER, SAP_PASSWORD
```

Solution: Set credentials in SSM Parameter Store or environment variables.

### MCP Server Connection Refused
```
Error: Connection refused when connecting to SAP MCP server
```

Solution:
1. Check SAP MCP container is running
2. Verify network connectivity between agent and MCP server
3. Check port 8000 is exposed

### SAP API Connection Errors
```
Error: HTTP 401 Unauthorized
```

Solution:
1. Verify SAP credentials
2. Check SAP host is accessible
3. Verify OData services are enabled in SAP

### Empty Evaluation Data
```
Warning: No data returned from SAP
```

Solution:
1. Verify SAP credentials and access
2. Check if specified materials/POs exist in SAP
3. Verify OData query syntax in test_sap_api.py

## Performance Considerations

- SAP MCP Server caches connections (retry logic with backoff)
- Queries have 30-second timeout
- Consider pagination for large result sets
- Use `$select` to limit fields returned

## Security Best Practices

1. **Store credentials securely:**
   - Use AWS SSM Parameter Store (never hardcode)
   - Use IAM roles for ECS task execution
   - Enable encryption at rest

2. **Network isolation:**
   - Run SAP MCP in private VPC
   - Restrict agent to SAP MCP communication only
   - Use security groups to limit access

3. **Audit logging:**
   - Enable CloudWatch logs
   - Track all SAP API calls
   - Monitor failed authentication attempts

## Next Steps

1. Deploy SAP MCP Server to ECS
2. Configure agent networking
3. Run evaluation on TST environment
4. Monitor logs and metrics
5. Deploy to PRD when satisfied

## References

- [SAP OData Services](https://help.sap.com/viewer/9a0e8ceb9615425daca12c6e30fc14ba/latest/en-US)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands Framework](https://github.com/strands-ai/strands)
