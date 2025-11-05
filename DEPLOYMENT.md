# SAP Agent UI Deployment Guide

## Quick Deployment to AWS App Runner

### Prerequisites
- AWS CLI configured with appropriate credentials
- Docker installed
- Terraform installed

### One-Command Deployment

Deploy to production:
```bash
./scripts/deploy-ui.sh prd
```

Deploy to test:
```bash
./scripts/deploy-ui.sh tst
```

### What the Script Does

1. **Creates Infrastructure** - Uses Terraform to create:
   - ECR repository for container images
   - IAM roles for App Runner
   - App Runner service with auto-scaling

2. **Builds Docker Image** - Packages the Flask UI into a container

3. **Pushes to ECR** - Uploads the container to AWS ECR

4. **Deploys** - App Runner automatically deploys the new image

5. **Returns URL** - You'll get an HTTPS URL like: `https://xxxxx.us-east-1.awsapprunner.com`

### Features

- **Auto-scaling**: Handles traffic spikes automatically
- **HTTPS**: SSL/TLS certificate automatically provisioned
- **Health checks**: Monitors `/health` endpoint
- **Auto-deploy**: Push to GitHub triggers deployment
- **IAM integration**: Service has permissions to call AgentCore

### Manual Steps (if script fails)

1. Create ECR repository:
```bash
cd terraform
terraform init
terraform apply -var="environment=prd"
```

2. Build and push Docker image:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_URL>
docker build -t sap-agent-ui:latest .
docker tag sap-agent-ui:latest <ECR_URL>:latest
docker push <ECR_URL>:latest
```

3. App Runner will auto-deploy when it detects the new image

### Monitoring

Check service status:
```bash
aws apprunner list-services --region us-east-1
aws apprunner describe-service --service-arn <SERVICE_ARN> --region us-east-1
```

View logs:
```bash
aws logs tail /aws/apprunner/sap-agent-ui-prd --follow
```

### Cost Estimate

- **App Runner**: ~$25/month for 1 vCPU, 2 GB RAM with moderate traffic
- **ECR**: ~$0.10/month for image storage
- **Data transfer**: Varies based on usage

### Troubleshooting

**Build fails**: Check Dockerfile and requirements-ui.txt
**Push fails**: Verify ECR login credentials
**Service won't start**: Check CloudWatch logs for errors
**Can't access agent**: Verify IAM role has AgentCore permissions

### Environment Variables

The service uses these environment variables:
- `PORT=8080` - Listen port
- `AGENT_ENV` - Either `TST` or `PRD`
- `PYTHONUNBUFFERED=1` - For proper logging

### Updating the Service

Simply run the deployment script again:
```bash
./scripts/deploy-ui.sh prd
```

App Runner will perform a rolling update with zero downtime.
