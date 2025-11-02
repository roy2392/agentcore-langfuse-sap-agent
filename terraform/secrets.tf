# AWS Secrets Manager for SAP credentials
resource "aws_secretsmanager_secret" "sap_credentials" {
  name        = "agentcore/sap/credentials-${var.environment}"
  description = "SAP OData API credentials for AgentCore Gateway"

  tags = {
    Name        = "sap-credentials-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "sap_credentials" {
  secret_id = aws_secretsmanager_secret.sap_credentials.id

  secret_string = jsonencode({
    SAP_HOST     = var.sap_host
    SAP_USER     = var.sap_user
    SAP_PASSWORD = var.sap_password
  })
}
