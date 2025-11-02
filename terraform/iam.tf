# IAM Role for AgentCore Gateway
resource "aws_iam_role" "gateway_role" {
  name = "AgentCoreGatewayRole-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "AgentCoreGatewayRole-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Policy for Gateway to invoke Lambda targets
resource "aws_iam_role_policy" "gateway_invoke_lambda" {
  name = "InvokeLambdaTargets"
  role = aws_iam_role.gateway_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.get_complete_po_data.arn,
          "${aws_lambda_function.get_complete_po_data.arn}:*"
        ]
      }
    ]
  })
}

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda_role" {
  name = "SAPToolsLambdaRole-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "SAPToolsLambdaRole-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Policy for Lambda to access Secrets Manager (for SAP credentials)
resource "aws_iam_role_policy" "lambda_secrets" {
  name = "AccessSAPCredentials"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.sap_credentials.arn
      }
    ]
  })
}
