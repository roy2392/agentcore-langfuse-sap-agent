# Archive the Lambda function code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda_functions"
  output_path = "${path.module}/lambda_package.zip"
}

# Lambda Layer for dependencies (requests, etc.)
resource "aws_lambda_layer_version" "python_dependencies" {
  filename            = "${path.module}/lambda_layer.zip"
  layer_name          = "sap-tools-dependencies-${var.environment}"
  compatible_runtimes = ["python3.12"]
  description         = "Python dependencies for SAP tools (requests, etc.)"
}

# Lambda function for get_complete_po_data
resource "aws_lambda_function" "get_complete_po_data" {
  depends_on = [aws_lambda_layer_version.python_dependencies]

  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "sap-get-complete-po-data-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "get_complete_po_data.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.12"
  timeout         = 30
  memory_size     = 512

  layers = [aws_lambda_layer_version.python_dependencies.arn]

  environment {
    variables = {
      SECRET_ARN = aws_secretsmanager_secret.sap_credentials.arn
    }
  }

  tags = {
    Name        = "sap-get-complete-po-data-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Tool        = "get_complete_po_data"
  }
}
