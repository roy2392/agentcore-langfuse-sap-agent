# Vercel Deployment Guide

## Quick Deploy (Automated via GitHub)

1. **Go to Vercel**: https://vercel.com/new
2. **Import your GitHub repository**: `roy2392/agentcore-langfuse-sap-agent`
3. **Select the branch**: `claude/deploy-frontend-vercel-011CUoRDC5GFPg57sShtKW2B`
4. **Configure the project**:
   - Framework Preset: Other
   - Root Directory: `./` (leave as is)
   - Build Command: (leave empty)
   - Output Directory: (leave empty)

5. **Add Environment Variables**:
   ```
   AGENT_ENV=PRD
   AWS_ACCESS_KEY_ID=<your_aws_access_key>
   AWS_SECRET_ACCESS_KEY=<your_aws_secret_key>
   AWS_DEFAULT_REGION=us-east-1
   ```

6. **Deploy to Barcelona Region**:
   - After first deployment, go to Project Settings → Functions
   - Select Region: **Frankfurt (fra1)** - closest to Barcelona
   - Redeploy

## Manual Deploy via CLI

```bash
# 1. Login to Vercel
vercel login

# 2. Deploy (first time)
vercel deploy

# 3. Deploy to production
vercel deploy --prod

# 4. Set environment variables
vercel env add AWS_ACCESS_KEY_ID
vercel env add AWS_SECRET_ACCESS_KEY
vercel env add AWS_DEFAULT_REGION
vercel env add AGENT_ENV
```

## Barcelona/Europe Region Configuration

To deploy close to Barcelona, use the Frankfurt region (closest to Spain):

1. In Vercel Dashboard → Project Settings → Functions
2. Select **Frankfurt (fra1)** as the region
3. This provides the lowest latency for European users

## AWS Credentials Setup

The app needs AWS credentials to invoke Bedrock agents. Options:

### Option 1: Environment Variables (Recommended for Vercel)
Add these in Vercel Dashboard → Environment Variables:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION=us-east-1`
- `AGENT_ENV=PRD`

### Option 2: IAM Role (if deploying on AWS)
Not applicable for Vercel deployment.

## Vercel Configuration Files

- `vercel.json` - Deployment configuration
- `.vercelignore` - Files to exclude from deployment

## Testing the Deployment

After deployment, test the endpoints:
```bash
# Health check
curl https://your-app.vercel.app/health

# Chat endpoint (requires AWS credentials)
curl -X POST https://your-app.vercel.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "environment": "PRD"}'
```

## Troubleshooting

### "No credentials found" error
- Make sure AWS credentials are set in Vercel environment variables
- Verify credentials have permission to invoke Bedrock agents

### Timeout errors
- Vercel free tier: 10s timeout
- Vercel Pro: 60s timeout
- If agent responses take longer, consider implementing streaming

### Region issues
- The app connects to AWS us-east-1 for Bedrock
- Vercel function can run in Frankfurt for lower latency to users
- Network latency between Vercel (Frankfurt) and AWS (us-east-1) is acceptable

## Next Steps

1. Deploy via GitHub integration (easiest)
2. Set environment variables in Vercel dashboard
3. Configure Frankfurt region for Barcelona users
4. Test the deployment
5. Monitor performance and adjust as needed
