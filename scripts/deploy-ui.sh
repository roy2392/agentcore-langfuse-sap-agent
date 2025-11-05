#!/bin/bash
set -e

# SAP Agent UI Deployment Script for AWS App Runner
# This script builds and deploys the UI to AWS App Runner

ENVIRONMENT="${1:-prd}"
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPOSITORY_NAME="sap-agent-ui-${ENVIRONMENT}"
IMAGE_TAG="latest"

echo "============================================================"
echo "Deploying SAP Agent UI to AWS App Runner"
echo "============================================================"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo "============================================================"

# Step 1: Apply Terraform to create ECR repository and App Runner service
echo ""
echo "[1/4] Creating AWS infrastructure with Terraform..."
cd terraform
terraform init
terraform apply -auto-approve -var="environment=${ENVIRONMENT}"

# Get ECR repository URL from Terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)
echo "ECR Repository: ${ECR_URL}"

cd ..

# Step 2: Build Docker image
echo ""
echo "[2/4] Building Docker image..."
docker build -t ${REPOSITORY_NAME}:${IMAGE_TAG} .

# Step 3: Login to ECR and push image
echo ""
echo "[3/4] Pushing image to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}
docker tag ${REPOSITORY_NAME}:${IMAGE_TAG} ${ECR_URL}:${IMAGE_TAG}
docker push ${ECR_URL}:${IMAGE_TAG}

# Step 4: App Runner will auto-deploy when new image is pushed
echo ""
echo "[4/4] App Runner is deploying the new image..."
echo "Waiting for deployment to complete..."

# Get service ARN
SERVICE_ARN=$(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='sap-agent-ui-${ENVIRONMENT}'].ServiceArn" --output text)

# Wait for service to be running
echo "Monitoring deployment status..."
while true; do
    STATUS=$(aws apprunner describe-service --service-arn ${SERVICE_ARN} --region ${AWS_REGION} --query 'Service.Status' --output text)
    echo "Status: ${STATUS}"
    
    if [ "${STATUS}" == "RUNNING" ]; then
        break
    elif [ "${STATUS}" == "OPERATION_IN_PROGRESS" ]; then
        echo "Deployment in progress..."
        sleep 10
    else
        echo "Unexpected status: ${STATUS}"
        exit 1
    fi
done

# Get the service URL
SERVICE_URL=$(aws apprunner describe-service --service-arn ${SERVICE_ARN} --region ${AWS_REGION} --query 'Service.ServiceUrl' --output text)

echo ""
echo "============================================================"
echo "✅ Deployment Complete!"
echo "============================================================"
echo "Service URL: https://${SERVICE_URL}"
echo "Environment: ${ENVIRONMENT}"
echo "============================================================"
echo ""
echo "You can now access the SAP Agent UI at the URL above."
echo ""
