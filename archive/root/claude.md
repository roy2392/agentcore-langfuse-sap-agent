Here is a comprehensive claude.md file (summary + practical guidance) based on the **Amazon Bedrock AgentCore Developer Guide**, tailored for Claude agent developers and integrators.

***

# Claude Agent Development on Amazon Bedrock AgentCore

## Overview

**Amazon Bedrock AgentCore** is a managed environment for building, deploying, and operating advanced AI agents, supporting multiple frameworks and model integrations. Its modular architecture supports runtime orchestration, persistent memory, secure identity, extensible tool access, observability, and robust security.

***

## Architecture Components

- **Runtime**
  - Manages agent execution lifecycle, provides API invocation, controls resource allocation, and handles agent-to-agent (A2A) and Model Control Plane (MCP) flows.[1][2][3][4][5][6]
  - Supports versioning, session management, header allowlists, streaming, and OAuth2 runtime authentication.[7][8][9][10]

- **Memory**
  - Persistent, long-term memory and retrieval-augmented generation (RAG) for agent context.[11][12][13][14][15]
  - Enables custom strategies for event management, consolidation, and contextual enrichment.

- **Gateway**
  - Securely connects agents to tools, services, and resources.[16][17][18][19][20][21][22][23][24]
  - Supports policy-based access, egress credential management, and integration with external APIs.

- **Identity**
  - Centralized identity management (workload identities, agent IDs, credential providers, tagging, and data protection).[25][26][27][28][29][30][31][32]
  - Abstraction for IAM roles, OAuth2 tokens, API keys. Identities persist across deployment environments and authentication schemes.

- **Built-in Tools**
  - API for browser automation, code execution, and integration capabilities.[33][34]
  - Useful for multi-modal agents and hybrid workflows.

- **Observability**
  - Telemetry, service-provided metrics, and configuration for debugging, monitoring, and performance analysis.[35][36][37][38][39][40][41]

- **Security & Compliance**
  - IAM best practices, confused deputy prevention, data protection, compliance validation, and disaster recovery.[42][32][43][44][45]

***

## Key Workflows & APIs

- **Deploying Agents**
  - Use Runtime and Gateway for automatic workload identity creation; manual identity creation for self-hosted/hybrid setups ([CreateWorkloadIdentity API]).[26][25]
  - Control access using credential providers scoped to workload identities.

- **Integrate Models & Frameworks**
  - Bring any model and framework (e.g., Claude) using Adapter APIs.[46][47]
  - MCP interface allows for coding assistant-style orchestration.[5][48]

- **Session Management**
  - Agents run in managed lifecycles, support streaming, async jobs, versioning, and fine-grained configuration.[49][9][10]

- **Memory Management**
  - Implement custom strategies via the Memory API (RAG, consolidation, extraction).[13][14][15]
  - Monitor usage and optimize token consumption.

- **Access External Resources**
  - Gateways can restrict or allow access to 3rd-party services, enforce policies, and integrate with both AWS and external APIs.[18][19]

***

## Best Practices

- **Identity and Access**
  - Use built-in identity abstraction for seamless credential management.
  - Tag identities for traceability and enforce least-privilege via fine-grained policies.

- **Security**
  - Enable cross-service confused deputy prevention; encrypt sensitive data at rest and in transit.
  - Validate compliance and audit settings regularly.

- **Observability**
  - Enable detailed telemetry; integrate with CloudWatch for alerting and dashboards.
  - Use built-in debugging and troubleshooting guides to resolve issues efficiently.

- **Scaling & Quotas**
  - Monitor service quotas (Runtime, Memory, Gateway, Identity, Browser, Code Interpreter).
  - Request quota increases as workloads expand.[50][51][52][53][54][55][56]

***

## Example Use Cases

- Deploy a Claude agent for enterprise document processing, leveraging RAG memory, Identity for OAuth2 credential flows, Gateway for API access, Observability for metrics, and Security for compliance validation.
- Build a multi-agent workflow orchestrated via MCP, integrating third-party APIs and maintaining persistent memory across sessions.
- Implement a browser-based tool agent to automate company web application interaction, leveraging AgentCore's built-in tools and secure browser context isolation.

***

## References

See [AWS Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/) for detailed API specs, configuration samples, and quick starts.

***

**This markdown provides practical, technical guidance for developing Claude-compatible agents on Amazon Bedrock AgentCore, covering architecture, workflows, APIs, and operational best practices for real-world enterprise integration.**

[1](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html)
[2](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html)
[3](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
[4](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-getting-started.html)
[5](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html)
[6](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)
[7](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
[8](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html)
[9](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html)
[10](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html)
[11](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-terminology.html)
[12](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
[13](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
[14](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-organization.html)
[15](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-ltm-rag.html)
[16](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-quick-start.html)
[17](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-core-concepts.html)
[18](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-features.html)
[19](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-supported-targets.html)
[20](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-prerequisites.html)
[21](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building.html)
[22](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using.html)
[23](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building-debug.html)
[24](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-advanced.html)
[25](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-overview.html)
[26](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-getting-started.html)
[27](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-how-to.html)
[28](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-manage-agent-ids.html)
[29](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-outbound-credential-provider.html)
[30](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idps.html)
[31](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-data-protection.html)
[32](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/security-iam.html)
[33](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)
[34](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html)
[35](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-observability.html)
[36](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-troubleshooting.html)
[37](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html)
[38](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
[39](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)
[40](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-service-provided.html)
[41](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-view.html)
[42](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/data-protection.html)
[43](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/compliance-validation.html)
[44](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/disaster-recovery-resiliency.html)
[45](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/cross-service-confused-deputy-prevention.html)
[46](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-agent-framework.html)
[47](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-model.html)
[48](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/mcp-getting-started.html)
[49](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html)
[50](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)
[51](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#runtime-service-limits)
[52](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#memory-limits)
[53](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#identity-service-limits)
[54](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#gateway-endpoints-quotas)
[55](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#browser-service-limits)
[56](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#code-interpreter-service-limits)
[57](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/understanding-agent-identities.html)
[58](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html)
[59](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html)