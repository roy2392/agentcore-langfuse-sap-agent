# Archive Directory

This directory contains archived files from previous development iterations. These files are kept for historical reference but are no longer actively used in the project.

## Archive Date
2025-11-03

## Archived Files

### Root Directory Files (`archive/root/`)
- `claude.md` - Temporary documentation file
- `evaluation_results_sap_po.json` - Old evaluation test results
- `test_agent_query.py` - Old agent testing script
- `test-sap-mcp.py` - Old SAP MCP testing script

### Agent Files (`archive/agents/`)
- `strands_claude_final.py` - Experimental agent version
- `strands_claude_mcp_agentcore_identity.py` - AgentCore identity-based version
- `strands_claude_mcp_gateway.py` - Early MCP Gateway integration attempt
- `strands_claude_working.py` - Working draft version (402 lines)
- `sigv4_mcp_client.py` - SigV4 authentication client (not used)
- `gateway_sigv4_transport.py` - SigV4 transport implementation (not used)

**Active Agent**: `agents/strands_claude.py` (current production version with OAuth)

### Utility Files (`archive/utils/`)
- `sap_mcp_server.py` - Old SAP MCP server implementation (282 lines)
- `sap_mcp_http_server.py` - HTTP-based MCP server (247 lines)
- `mcp_server.py` - Generic MCP server (262 lines)
- `test_sap_api.py` - SAP API testing utilities (513 lines)

**Active Utilities**:
- `utils/agent.py` - Agent deployment and management
- `utils/langfuse.py` - Langfuse integration
- `utils/aws.py` - AWS utilities
- `utils/gateway.py` - Gateway utilities
- `utils/test_e2e_agent.py` - End-to-end testing
- `utils/test_mcp_gateway.py` - MCP Gateway testing

### CI/CD Files (`archive/cicd/`)
- `deploy_sap_mcp.py` - Old SAP MCP deployment (280 lines)
- `deploy_with_gateway.py` - Old Gateway deployment script
- `evaluate_with_sap_mcp.py` - Old evaluation with SAP MCP (554 lines)
- `test_sap_mcp_locally.py` - Local SAP MCP testing (243 lines)
- `sap_mcp_config.json` - Old SAP MCP configuration
- `generate_sap_evaluation_data.py` - SAP evaluation data generator (262 lines)
- `generate_po_evaluation_data.py` - PO evaluation data generator (260 lines)
- `tst_sap_po.py` - SAP PO testing script (288 lines)

**Active CI/CD Scripts**:
- `cicd/deploy_agent.py` - Current agent deployment
- `cicd/delete_agent.py` - Agent cleanup
- `cicd/check_factuality.py` - Factuality validation
- `cicd/tst.py` - Testing utilities

### Terraform Files (`archive/terraform/`)
- `update_gateway.py` - Old Gateway update script
- `target_config.json` - Old target configuration
- `target_output.json` - Old target output
- `gateway_create_config.json` - Old Gateway creation config
- `Dockerfile 2.sap-mcp` - Old SAP MCP Dockerfile
- `Dockerfile.sap-mcp` - Another old Dockerfile

**Active Terraform Files**:
- `terraform/main.tf` - Main Terraform configuration
- `terraform/gateway.tf` - MCP Gateway infrastructure
- `terraform/cognito.tf` - AWS Cognito OAuth configuration
- `terraform/lambda.tf` - Lambda function infrastructure
- `terraform/iam.tf` - IAM roles and policies
- `terraform/secrets.tf` - Secrets Manager configuration

## Reason for Archiving

These files were archived during a code cleanup and reorganization effort (2025-11-03) to:

1. **Reduce Complexity**: Remove experimental and obsolete code paths
2. **Improve Maintainability**: Keep only actively used implementation
3. **Simplify Onboarding**: Make it easier for new developers to understand the current architecture
4. **Historical Reference**: Preserve old implementations for reference

## Current Architecture

The project now uses a streamlined architecture:

- **Agent**: OAuth-based MCP Gateway integration (`agents/strands_claude.py`)
- **Gateway**: AWS Bedrock AgentCore Gateway with CUSTOM_JWT authorization
- **Authentication**: AWS Cognito OAuth 2.0 (Client Credentials flow)
- **Lambda**: SAP OData integration via `get_complete_po_data.py`
- **Testing**: MCP Inspector and E2E testing scripts

## Recovery

If you need to recover any of these archived files, they can be moved back to their original locations. However, please review the current implementation first, as the architecture may have evolved significantly.

## Questions

If you have questions about why specific files were archived or need to understand the historical context, please refer to:
- Git history for detailed change logs
- Current README.md for up-to-date architecture documentation
- ARCHITECTURE.md for system design overview
