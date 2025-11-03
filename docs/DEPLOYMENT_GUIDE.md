# SAP MCP Server - Complete Deployment Guide

This guide walks through deploying and validating the SAP MCP Server integration with your Bedrock AgentCore inventory management agent.

## Quick Summary

- **SAP MCP Server**: Exposes 8 SAP inventory tools via Model Context Protocol
- **Agent Integration**: Updated to use SAP MCP for real-time data access
- **Evaluation**: Validates agent responses against actual SAP data
- **Deployment**: Docker containerized with AWS ECR/ECS support

## Phase 1: Local Validation (5 minutes)

### Step 1.1: Verify Prerequisites

```bash
# Check Python version
python --version  # Should be 3.11+

# Check Docker
docker --version

# Check AWS CLI
aws --version
aws sts get-caller-identity  # Verify AWS credentials
```

### Step 1.2: Test Local SAP Connectivity

```bash
# Set SAP credentials (get from your SAP system)
export SAP_HOST="sap-server.example.com"
export SAP_USER="your_username"
export SAP_PASSWORD="your_password"

# Test SAP API directly
python utils/test_sap_api.py
```

**Expected output:**
```
metadata_probe: {'status': 'success', 'data': '...'}
Purchase order data: {...}
```

### Step 1.3: Run Local SAP MCP Tests

```bash
# Run comprehensive test suite
python cicd/test_sap_mcp_locally.py
```

**Expected output:**
```
TEST 1: SAP API Connectivity ✓
TEST 2: MCP Tool Discovery ✓
TEST 3: MCP Tool Execution ✓
TEST 4: Docker Image Build ✓
TEST 5: Evaluation Data Format ✓

TEST REPORT SUMMARY
✓ All tests passed! SAP MCP is ready for deployment.
```

### Step 1.4: Test SAP MCP Evaluation (Local)

```bash
# Run evaluation using SAP MCP server
python cicd/evaluate_with_sap_mcp.py
```

**Expected output:**
```
EVALUATION: Stock Level Query
1. Fetching SAP data via MCP server...
2. SAP Response: Material 100-100: 150 available
3. Expected Hebrew Response: כמות המלאי של המוצר 100-100...

EVALUATION SUMMARY
✓ stock_level_query: 1.00
✓ low_stock_query: 0.95
✓ po_status_query: 0.90
✓ warehouse_query: 0.92

Average Quality Score: 0.944 (94.4%)
Results saved to: sap_mcp_evaluation_results.json
```

---

## Phase 2: AWS Deployment (15 minutes)

### Step 2.1: Store SAP Credentials in AWS SSM

```bash
# Set region (match your AWS account region)
export AWS_REGION="us-east-1"

# Store credentials securely
aws ssm put-parameter \
  --name /sap/SAP_HOST \
  --value "$SAP_HOST" \
  --type SecureString \
  --region $AWS_REGION

aws ssm put-parameter \
  --name /sap/SAP_USER \
  --value "$SAP_USER" \
  --type SecureString \
  --region $AWS_REGION

aws ssm put-parameter \
  --name /sap/SAP_PASSWORD \
  --value "$SAP_PASSWORD" \
  --type SecureString \
  --region $AWS_REGION

# Verify stored
aws ssm get-parameter --name /sap/SAP_HOST --region $AWS_REGION --with-decryption
```

### Step 2.2: Deploy SAP MCP Server to AWS

```bash
# Deploy to ECR and optionally ECS
python cicd/deploy_sap_mcp.py \
  --region us-east-1 \
  --tag latest \
  --deploy-ecs \
  --task-family sap-mcp-server

# Output:
# ✓ ECR repository created: 123456789.dkr.ecr.us-east-1.amazonaws.com/sap-mcp-server
# ✓ Docker image pushed
# ✓ ECS task definition registered
# ✓ Deployment config saved to: cicd/sap_mcp_config.json
```

### Step 2.3: Verify SAP MCP Server is Running

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster default \
  --services sap-mcp-server \
  --region us-east-1

# View logs
aws logs tail /ecs/sap-mcp-server --follow --region us-east-1

# Expected log output:
# SAP MCP Server started on port 8000
# Health check: SAP credentials validated
```

### Step 2.4: Test SAP MCP Server Connectivity

```bash
# Get SAP MCP Server IP/endpoint
SAP_MCP_IP=$(aws ecs describe-tasks --cluster default --tasks <task-arn> --region us-east-1 | jq -r '.tasks[0].containerInstanceArn')

# Test endpoint
curl -f http://$SAP_MCP_IP:8000/health

# Expected: HTTP 200 with credential validation result
```

---

## Phase 3: Agent Deployment to TST (10 minutes)

### Step 3.1: Deploy Agent with SAP MCP Configuration

```bash
# Set environment variables for agent
export SAP_MCP_HOST="sap-mcp-server"  # Or IP if not using DNS
export SAP_MCP_PORT="8000"
export BEDROCK_MODEL_ID="anthropic.claude-3-sonnet-20240229-v1:0"

# Deploy to TST environment
python cicd/deploy_agent.py \
  --environment TST \
  --model-id "$BEDROCK_MODEL_ID"

# Output:
# ✓ Agent deployed: strands_sonnet3_hebinv_TST-<random>
# ✓ Configuration saved to: cicd/agent_config.json
```

### Step 3.2: Verify Agent Deployment

```bash
# Check agent status
aws bedrock-agent list-agents --region us-east-1

# Test agent invocation (if available)
python cicd/test_agent_invocation.py \
  --agent-id strands_sonnet3_hebinv_TST \
  --question "מה כמות המלאי של המוצר 100-100?"

# Expected response in Hebrew with stock data
```

---

## Phase 4: Evaluation (5 minutes)

### Step 4.1: Run TST Evaluation

```bash
# Run evaluation against TST agent
python cicd/tst.py

# This will:
# 1. Load evaluation dataset from Langfuse
# 2. Invoke agent for each test case
# 3. Evaluate responses using Bedrock Claude
# 4. Save results to: evaluation_results.json
```

### Step 4.2: Check Evaluation Results

```bash
# Review results
python cicd/check_factuality.py --threshold 0.7

# Expected output:
# Experiment: Hebrew Inventory Agent - Bedrock Evaluation
# Total items evaluated: 5
# Average Quality Score (Bedrock Claude): 0.850 (85.0%)
#
# ✓ PASSED: Quality score 85.0% is above 70.0%
```

### Step 4.3: Review Individual Scores

```bash
# View detailed results
cat evaluation_results.json | jq '.scores[]'

# Expected structure:
# {
#   "name": "bedrock_quality",
#   "value": 0.92,
#   "comment": "Quality score from Claude evaluation: 0.92"
# }
```

---

## Phase 5: Production Deployment (10 minutes)

### Step 5.1: Deploy Agent to PRD

```bash
# Deploy to production when TST score acceptable
python cicd/deploy_agent.py \
  --environment PRD \
  --model-id "$BEDROCK_MODEL_ID"

# Output:
# ✓ Agent deployed to PRD: strands_sonnet3_hebinv_PRD-<random>
```

### Step 5.2: Verify PRD Deployment

```bash
# List all agents
aws bedrock-agent list-agents --region us-east-1

# Test PRD agent with real query
python cicd/test_agent_invocation.py \
  --agent-id strands_sonnet3_hebinv_PRD \
  --question "אילו מוצרים יש לנו במלאי נמוך?"
```

---

## Testing & Verification Checklist

### Local Testing
- [ ] SAP API connectivity verified
- [ ] MCP server tool discovery working
- [ ] MCP tools execute successfully
- [ ] Docker image builds without errors
- [ ] Evaluation data format is correct
- [ ] SAP MCP evaluation passes (avg score > 0.7)

### AWS Deployment
- [ ] SAP credentials stored in SSM Parameter Store
- [ ] ECR repository created and image pushed
- [ ] ECS task definition registered
- [ ] SAP MCP container running and healthy
- [ ] SAP MCP endpoint accessible

### Agent Integration
- [ ] Agent deployed to TST environment
- [ ] Agent can invoke SAP MCP tools
- [ ] Hebrew responses returned correctly
- [ ] Response latency acceptable (<10 seconds)

### Evaluation
- [ ] TST evaluation runs successfully
- [ ] Quality score meets threshold (≥70%)
- [ ] Individual scores reviewed and acceptable
- [ ] No authentication/permission errors

### Production Deployment
- [ ] PRD agent deployed successfully
- [ ] PRD agent responds to Hebrew queries
- [ ] All SAP tools accessible from PRD agent
- [ ] Monitoring/alerting configured

---

## Troubleshooting

### SAP Credentials Missing
```bash
# Error: Missing env vars: SAP_HOST, SAP_USER, SAP_PASSWORD
# Solution:
export SAP_HOST="your-host"
export SAP_USER="your-user"
export SAP_PASSWORD="your-password"
```

### SAP Connection Refused
```bash
# Error: HTTP Error 401: Unauthorized
# Solutions:
# 1. Verify credentials are correct
aws ssm get-parameter --name /sap/SAP_HOST --region us-east-1 --with-decryption

# 2. Verify SAP host is accessible
ping $SAP_HOST

# 3. Test SAP API directly
python utils/test_sap_api.py
```

### MCP Server Not Found
```bash
# Error: Connection refused when connecting to MCP server
# Solutions:
# 1. Check ECS task is running
aws ecs describe-tasks --cluster default --tasks <task-arn> --region us-east-1

# 2. Check logs for errors
aws logs tail /ecs/sap-mcp-server --region us-east-1

# 3. Verify networking
curl -f http://$SAP_MCP_IP:8000/health
```

### Agent Evaluation Fails
```bash
# Error: Agent invocation failed
# Solutions:
# 1. Check agent deployment
python cicd/test_agent_invocation.py --agent-id <agent-id>

# 2. Review agent logs in CloudWatch
aws logs describe-log-groups --region us-east-1 | grep agent

# 3. Verify Langfuse dataset exists
# The evaluation dataset should be named: strands-ai-mcp-agent-evaluation
```

### Low Quality Scores
```bash
# If evaluation scores < 0.7:
# 1. Check if SAP data is correct
python cicd/evaluate_with_sap_mcp.py

# 2. Review agent responses
cat evaluation_results.json

# 3. Adjust evaluation threshold if needed
python cicd/check_factuality.py --threshold 0.65
```

---

## Performance Benchmarks

Expected performance characteristics:

| Operation | Time | Notes |
|-----------|------|-------|
| SAP stock level query | 1-2s | Depends on SAP system |
| Low stock scan | 2-3s | Full table scan |
| PO lookup | ~1s | Indexed query |
| MCP tool execution | <100ms | Local execution |
| Agent reasoning | 3-5s | Claude model inference |
| Total response | 5-8s | End-to-end latency |

---

## Monitoring & Logging

### CloudWatch Logs

```bash
# SAP MCP Server logs
aws logs tail /ecs/sap-mcp-server --follow --region us-east-1

# Agent logs
aws logs tail /aws/bedrock/agents/<agent-id> --follow --region us-east-1

# Evaluation logs
tail -f evaluation_results.json
```

### Key Metrics to Monitor

1. **Agent Response Time**: Should be <10 seconds
2. **Evaluation Score**: Should be >0.7
3. **SAP API Success Rate**: Should be >95%
4. **MCP Tool Success Rate**: Should be >98%
5. **Error Rate**: Should be <2%

---

## Security Best Practices

✓ Store credentials in AWS SSM Parameter Store (encrypted)
✓ Use IAM roles for ECS task execution
✓ Restrict agent/MCP communication to internal VPC
✓ Enable CloudWatch logging for audit trails
✓ Rotate SAP credentials regularly
✓ Monitor for unusual API call patterns
✓ Use HTTPS for external communication
✓ Implement rate limiting on SAP API calls

---

## Maintenance & Updates

### Regular Tasks

- **Weekly**: Review CloudWatch logs for errors
- **Monthly**: Check SAP API response times
- **Quarterly**: Update Docker base image (security patches)
- **Quarterly**: Review and rotate SAP credentials
- **As needed**: Update agent system prompt for new requirements

### Updating SAP MCP Server

```bash
# Make changes to utils/sap_mcp_server.py
# Rebuild and push to ECR
python cicd/deploy_sap_mcp.py --region us-east-1 --tag v1.1

# Update ECS task definition
python cicd/deploy_sap_mcp.py --region us-east-1 --deploy-ecs --task-family sap-mcp-server

# Rolling update (ECS handles automatically)
```

### Updating Agent

```bash
# Make changes to agents/strands_claude.py
# Rebuild and push to ECR
python cicd/deploy_agent.py --environment TST

# Run evaluation to verify
python cicd/tst.py

# Deploy to PRD when satisfied
python cicd/deploy_agent.py --environment PRD
```

---

## Support & Documentation

- **Setup Issues**: See Phase 1 & 2 above
- **SAP Integration**: See `SAP_MCP_DEPLOYMENT.md`
- **MCP Tools Reference**: See `SAP_MCP_DEPLOYMENT.md` → "MCP Tools Reference"
- **Evaluation**: See `QUICK_START_SAP_MCP.md` → "Available Tools"
- **Troubleshooting**: See "Troubleshooting" section above

---

## Next Steps

1. ✓ Follow Phase 1 for local validation
2. ✓ Follow Phase 2 for AWS deployment
3. ✓ Follow Phase 3 for agent deployment to TST
4. ✓ Follow Phase 4 for evaluation
5. ✓ Follow Phase 5 for production deployment

**Estimated total time**: 40 minutes (includes testing at each phase)

---

## Summary

You now have a production-ready SAP MCP Server integrated with your Bedrock AgentCore agent. The agent can handle Hebrew-language inventory queries with real-time data from your SAP system.

Key capabilities:
- ✓ 8 SAP inventory management tools
- ✓ Hebrew-language responses
- ✓ Real-time SAP data access
- ✓ Docker containerized deployment
- ✓ AWS ECR/ECS integration
- ✓ Comprehensive evaluation framework
- ✓ Security best practices

For questions or issues, refer to the troubleshooting section or the comprehensive documentation in the repository.
