# AWS AgentCore Gateway Architecture

## Overview

This project implements an SAP inventory management agent using **AWS Bedrock AgentCore** with **Lambda-based tool execution**, following AWS best practices for secure, scalable AI agents.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      USER REQUEST                            │
│                  "What purchase orders are open?"            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               BEDROCK AGENTCORE RUNTIME                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SAP Inventory Agent                                 │  │
│  │  - Model: Claude 3.5 Sonnet                          │  │
│  │  - System Prompt: cicd/system_prompt_english.txt     │  │
│  │  - NO direct SAP API calls                           │  │
│  │  - NO embedded credentials                           │  │
│  │  - Uses Gateway endpoint for all tools               │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          │ GATEWAY_ENDPOINT_URL
                          │ (OAuth 2.0 Bearer Token)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENTCORE GATEWAY                               │
│              sap-inventory-gateway-prd                       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Inbound Authentication                            │    │
│  │  - AWS Cognito OAuth 2.0                           │    │
│  │  - Client Credentials Flow                         │    │
│  │  - JWT Token Validation                            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  MCP Protocol Handler                              │    │
│  │  - tools/list                                      │    │
│  │  - tools/call                                      │    │
│  │  - resources/* (future)                            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Gateway Targets (Lambda Functions)                │    │
│  │  ✓ sap-tools-prd (7 tools)                         │    │
│  │  ✓ sap-get-complete-po-data-prd (1 tool)           │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ AWS Lambda Invocation
                           │ (IAM Authorization)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               LAMBDA FUNCTIONS                               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  sap-tools-prd                                     │    │
│  │  Handler: lambda_functions/sap_tools.py            │    │
│  │  Runtime: Python 3.12                              │    │
│  │  Timeout: 60s | Memory: 512MB                      │    │
│  │                                                     │    │
│  │  Tools:                                            │    │
│  │  1. get_material_stock                             │    │
│  │  2. get_open_purchase_orders                       │    │
│  │  3. get_orders_awaiting_invoice_or_delivery        │    │
│  │  4. get_inventory_with_open_orders                 │    │
│  │  5. get_goods_receipts                             │    │
│  │  6. list_purchase_orders                           │    │
│  │  7. search_purchase_orders                         │    │
│  │  8. get_material_in_transit                        │    │
│  │  9. get_orders_in_transit                          │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  sap-get-complete-po-data-prd                      │    │
│  │  Handler: lambda_functions/get_complete_po_data.py │    │
│  │  Runtime: Python 3.12                              │    │
│  │  Timeout: 30s | Memory: 512MB                      │    │
│  │                                                     │    │
│  │  Tool:                                             │    │
│  │  1. get_complete_po_data                           │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ SAP Credentials
                           │ (from Secrets Manager)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 SAP ODATA API                                │
│                                                              │
│  Host: aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev  │
│  User: AWSDEMO                                              │
│  Auth: Basic Auth (from Secrets Manager)                    │
│                                                              │
│  Available Services:                                        │
│  ✅ Purchase Order API (API_PURCHASEORDER_PROCESS_SRV)      │
│  ✅ Material Document API (API_MATERIAL_DOCUMENT_SRV)       │
│  ⚠️  Material Stock API (403 - Limited permissions)         │
│  ⚠️  Goods Receipt API (403 - Limited permissions)          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           AWS SECRETS MANAGER                                │
│           (Credential Storage)                               │
│                                                              │
│  Secret: agentcore/sap/credentials-prd                      │
│  {                                                           │
│    "SAP_HOST": "aws-saptfc-demosystems-...",               │
│    "SAP_USER": "AWSDEMO",                                   │
│    "SAP_PASSWORD": "***"                                    │
│  }                                                           │
│                                                              │
│  - Encrypted at rest (AWS KMS)                              │
│  - Accessed by Lambda IAM role                              │
│  - NOT embedded in code or environment                      │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Bedrock AgentCore Runtime

**Purpose**: Hosts and executes the AI agent

**Features**:
- Managed runtime environment
- Built-in session management
- Automatic tool discovery and invocation
- Streaming response support

**Agent Configuration**:
```json
{
  "agent_name": "strands_s3_english_PRD",
  "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
  "system_prompt_file": "cicd/system_prompt_english.txt",
  "gateway_url": "https://gateway-id.gateway.bedrock-agentcore..."
}
```

### 2. AgentCore Gateway

**Purpose**: Secure, managed gateway between agent and tools

**Features**:
- ✅ **OAuth 2.0 Authentication**: Cognito-based token validation
- ✅ **MCP Protocol**: Standard Model Context Protocol support
- ✅ **Lambda Integration**: Direct Lambda function invocation
- ✅ **IAM Authorization**: Fine-grained access control
- ✅ **CloudWatch Logging**: Full audit trail

**Gateway Targets**:
```
Target: sap-tools-lambda
  Type: AWS Lambda
  ARN: arn:aws:lambda:us-east-1:xxx:function:sap-tools-prd
  Tools: 9 inventory management tools

Target: sap-complete-po-lambda
  Type: AWS Lambda
  ARN: arn:aws:lambda:us-east-1:xxx:function:sap-get-complete-po-data-prd
  Tools: 1 comprehensive PO tool
```

### 3. AWS Cognito OAuth

**Purpose**: Secure authentication for Gateway access

**Configuration**:
- **User Pool**: `sap-gateway-oauth-prd`
- **Resource Server**: `sap-gateway-prd`
- **OAuth Scope**: `sap-gateway-prd/tools.invoke`
- **Flow**: Client Credentials (machine-to-machine)

**Token Exchange**:
```bash
POST https://sap-gateway-prd-123456789.auth.us-east-1.amazoncognito.com/oauth2/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=sap-gateway-prd/tools.invoke

Response:
{
  "access_token": "eyJraWQiOiI...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### 4. Lambda Functions

**Purpose**: Execute SAP tool logic with credential injection

**Function 1: sap-tools-prd**
- **Handler**: `sap_tools.lambda_handler`
- **Tools**: 9 inventory management tools
- **Runtime**: Python 3.12
- **Dependencies**: `requests` library (via Lambda Layer)
- **Timeout**: 60 seconds
- **Memory**: 512 MB

**Function 2: sap-get-complete-po-data-prd**
- **Handler**: `get_complete_po_data.lambda_handler`
- **Tools**: 1 comprehensive PO data tool
- **Runtime**: Python 3.12
- **Timeout**: 30 seconds
- **Memory**: 512 MB

**Environment Variables**:
```bash
SECRET_ARN=arn:aws:secretsmanager:us-east-1:xxx:secret:agentcore/sap/credentials-prd-xxx
```

**IAM Permissions**:
- ✅ `secretsmanager:GetSecretValue` - Read SAP credentials
- ✅ CloudWatch Logs write access

### 5. AWS Secrets Manager

**Purpose**: Secure storage of SAP credentials

**Secret Structure**:
```json
{
  "SAP_HOST": "aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev",
  "SAP_USER": "AWSDEMO",
  "SAP_PASSWORD": "***"
}
```

**Security**:
- Encrypted at rest with AWS KMS
- Encrypted in transit (TLS)
- Access via IAM policies only
- Rotation supported (manual or automatic)

## Data Flow

### Example: User Query Processing

1. **User Request**:
   ```
   User: "What are the details of purchase order 4500000520?"
   ```

2. **Agent Processing**:
   - Agent receives query
   - Analyzes system prompt: "Use get_complete_po_data tool"
   - Constructs tool call request

3. **Gateway Authentication**:
   - Agent includes OAuth Bearer token in request
   - Gateway validates token with Cognito
   - Gateway authorizes tool access

4. **Tool Invocation**:
   - Gateway invokes Lambda function: `sap-get-complete-po-data-prd`
   - Lambda retrieves SAP credentials from Secrets Manager
   - Lambda makes SAP OData API call
   - Lambda returns formatted response

5. **Response to User**:
   ```
   Agent: "Purchase Order 4500000520:
   - Supplier: ABC Corp
   - Date: 2024-08-15
   - Total: $209,236.00
   - 7 items
   - Status: Open"
   ```

## Security Architecture

### Defense in Depth

```
Layer 1: AWS IAM
  ↓ Controls who can deploy/manage infrastructure

Layer 2: OAuth 2.0 (Cognito)
  ↓ Controls who can access Gateway

Layer 3: Gateway Authorization
  ↓ Controls which tools can be invoked

Layer 4: Lambda IAM Role
  ↓ Controls Lambda access to Secrets Manager

Layer 5: Secrets Manager
  ↓ Stores encrypted SAP credentials

Layer 6: SAP API
  ↓ Final authentication with SAP system
```

### Credential Flow (Secure)

```
✅ GOOD (Current Architecture):

Agent → Gateway (OAuth token) → Lambda → Secrets Manager → SAP API
                                    ↑
                              IAM Role grants
                              secretsmanager:GetSecretValue
```

### What We Avoid (Insecure)

```
❌ BAD (Hardcoded):
Agent (with embedded SAP credentials) → SAP API

❌ BAD (Environment Variables):
Agent → Lambda (SAP_USER/SAP_PASSWORD in env vars) → SAP API
```

## Deployment Architecture

### Infrastructure as Code (Terraform)

```
terraform/
├── main.tf           # Provider and backend configuration
├── cognito.tf        # OAuth user pool and resource server
├── gateway.tf        # AgentCore Gateway and targets
├── lambda.tf         # Lambda functions and layers
├── secrets.tf        # Secrets Manager secret
├── iam.tf            # IAM roles and policies
└── gateway_output.json  # Output for agent deployment
```

### Deployment Workflow

```
1. Terraform Apply
   ↓ Creates infrastructure
   ↓ Outputs gateway_url, cognito_client_id, etc.

2. Save Configuration
   ↓ terraform/gateway_output.json

3. Deploy Agent (cicd/deploy_agent.py)
   ↓ Reads gateway_output.json
   ↓ Reads system_prompt_english.txt
   ↓ Calls AgentCore API to create agent

4. Test Agent (cicd/tst.py)
   ↓ Invokes agent with test queries
   ↓ Validates tool execution
   ↓ Checks Langfuse traces
```

## Tool Catalog

| Tool Name | Lambda Function | Purpose | SAP API Endpoint |
|-----------|----------------|---------|------------------|
| get_material_stock | sap-tools-prd | Get material inventory levels | API_MATERIAL_STOCK_SRV |
| get_open_purchase_orders | sap-tools-prd | List open POs | API_PURCHASEORDER_PROCESS_SRV |
| get_orders_awaiting_invoice_or_delivery | sap-tools-prd | Find orders with issues | API_PURCHASEORDER_PROCESS_SRV |
| get_inventory_with_open_orders | sap-tools-prd | Combined view | Multiple APIs |
| get_goods_receipts | sap-tools-prd | Recent receipts | API_MATERIAL_DOCUMENT_SRV |
| list_purchase_orders | sap-tools-prd | List all POs | API_PURCHASEORDER_PROCESS_SRV |
| search_purchase_orders | sap-tools-prd | Search specific PO | API_PURCHASEORDER_PROCESS_SRV |
| get_material_in_transit | sap-tools-prd | Materials in transit | API_PURCHASEORDER_PROCESS_SRV |
| get_orders_in_transit | sap-tools-prd | POs in transit | API_PURCHASEORDER_PROCESS_SRV |
| get_complete_po_data | sap-get-complete-po-data-prd | Complete PO details | API_PURCHASEORDER_PROCESS_SRV |

## Observability

### CloudWatch Logs

```
Log Groups:
- /aws/lambda/sap-tools-prd
- /aws/lambda/sap-get-complete-po-data-prd
- /aws/bedrock-agentcore/agents/<agent-id>
- /aws/bedrock-agentcore/gateway/<gateway-id>
```

### Langfuse Integration (Optional)

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="https://cloud.langfuse.com"
)

# Automatic trace collection for agent invocations
```

### Metrics

Key metrics to monitor:
- Agent invocation count
- Tool execution latency
- Lambda duration and errors
- SAP API response times
- OAuth token validation success rate

## Scalability

### Current Limits

| Component | Limit | Notes |
|-----------|-------|-------|
| Lambda Concurrency | 1000 (default) | Can increase via quota request |
| Lambda Timeout | 60s (sap-tools) | Configurable in terraform/lambda.tf |
| Gateway Targets | 10 per gateway | Sufficient for current tools |
| Cognito MAU | 50,000 (free tier) | Machine-to-machine doesn't count |

### Scaling Strategies

**Horizontal Scaling**:
- Lambda automatically scales to handle concurrent requests
- Gateway distributes load across Lambda invocations

**Vertical Scaling**:
- Increase Lambda memory allocation (currently 512 MB)
- Increase Lambda timeout (currently 30-60s)

**Performance Optimization**:
- Use Lambda reserved concurrency for predictable performance
- Enable Lambda SnapStart for faster cold starts (when supported for Python 3.12)
- Cache SAP API responses in Lambda (with TTL)

## Cost Optimization

### Current Architecture Cost Breakdown

**Monthly estimate (10,000 agent queries)**:
- AgentCore Gateway: ~$0 (preview, pricing TBD)
- Lambda invocations: ~$0.20
- Lambda duration (10K × 2s avg): ~$0.03
- Secrets Manager: $0.40
- CloudWatch Logs: ~$0.50
- **Total**: **< $2/month**

**At scale (1M agent queries/month)**:
- Lambda invocations: ~$20
- Lambda duration: ~$3
- Other services: ~$1
- **Total**: **< $25/month**

## Comparison to Alternatives

| Architecture | Pros | Cons |
|-------------|------|------|
| **Lambda (Current)** | ✅ Serverless, scales automatically<br>✅ Pay-per-use pricing<br>✅ Integrated with AgentCore Gateway | ⚠️ Cold start latency<br>⚠️ 60s timeout limit |
| Container (ECS/Fargate) | ✅ Long-running processes<br>✅ Custom dependencies | ❌ Higher cost (always running)<br>❌ More complex deployment |
| Direct Agent→SAP | ✅ Lower latency | ❌ Security risk (embedded credentials)<br>❌ Not AWS best practice |

## Future Enhancements

### Planned Improvements

1. **VPC Integration**:
   - Deploy Lambda in VPC for private SAP access
   - Use VPC endpoints for Secrets Manager

2. **Caching Layer**:
   - Add ElastiCache/DynamoDB for SAP response caching
   - Reduce SAP API calls

3. **Additional Tools**:
   - Material master data queries
   - Vendor information lookups
   - Inventory forecasting

4. **Multi-tenancy**:
   - Support multiple SAP systems
   - Per-customer credential isolation

5. **Streaming Responses**:
   - Enable agent streaming for longer queries
   - Improve user experience for complex analyses

## References

- [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Cognito OAuth 2.0](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-userpools-server-side-client-credentials.html)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
