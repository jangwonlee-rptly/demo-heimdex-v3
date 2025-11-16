# Railway CLI Deployment Guide

Step-by-step guide to deploy Heimdex using Railway CLI.

## Prerequisites

- [x] Railway CLI installed: `npm i -g @railway/cli`
- [x] Logged in: `railway login`
- [ ] In project directory: `cd /path/to/demo-heimdex-v3`

## Step 1: Initialize Railway Project

```bash
# Make sure you're in the project root
cd /home/ljin/Projects/demo-heimdex-v3

# Initialize a new Railway project
railway init

# When prompted:
# - Project name: demo-heimdex-v3 (or your preferred name)
# - This creates a new project in your Railway account
```

**Alternative**: If you already created a project in the Railway dashboard:
```bash
railway link
# Select your existing project from the list
```

## Step 2: Create Redis Database

Railway databases are created through the dashboard (not CLI). You have two options:

**Option A: Using Railway Dashboard**
1. Go to https://railway.app/dashboard
2. Open your project
3. Click "+ New" → "Database" → "Redis"
4. Redis is now created

**Option B: Using CLI to open dashboard**
```bash
# Open your project in browser
railway open
# Then click "+ New" → "Database" → "Redis" in the UI
```

The Redis service will auto-generate a `REDIS_URL` variable that other services can reference.

## Step 3: Deploy API Service

```bash
# Create a new service for the API
railway service create api

# Deploy the API service
cd services/api
railway up --service api

# This will:
# - Build the Docker image from services/api/Dockerfile
# - Deploy the container
# - Assign a public URL (if needed)
```

**Set API environment variables:**
```bash
# Make sure you're working with the api service
railway service --name api

# Set variables (replace with your actual values)
railway variables set SUPABASE_URL=https://your-project.supabase.co
railway variables set SUPABASE_ANON_KEY=your-anon-key-here
railway variables set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
railway variables set SUPABASE_JWT_SECRET=your-jwt-secret-here
railway variables set DATABASE_URL=postgresql://postgres:password@host:5432/postgres
railway variables set OPENAI_API_KEY=sk-your-openai-api-key-here

# Reference Redis URL from Redis service (Railway will resolve this)
railway variables set REDIS_URL='${{Redis.REDIS_URL}}'

# CORS - will update this after frontend is deployed
railway variables set API_CORS_ORIGINS=http://localhost:3000
```

**Enable public networking for API:**
```bash
# Generate a public domain for the API
railway domain

# Note the domain (e.g., api-production-abc123.up.railway.app)
# You'll need this for the frontend configuration
```

## Step 4: Deploy Worker Service

```bash
# Go back to project root
cd /home/ljin/Projects/demo-heimdex-v3

# Create worker service
railway service create worker

# Deploy worker
cd services/worker
railway up --service worker
```

**Set Worker environment variables:**
```bash
# Switch to worker service
railway service --name worker

# Set variables
railway variables set SUPABASE_URL=https://your-project.supabase.co
railway variables set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
railway variables set DATABASE_URL=postgresql://postgres:password@host:5432/postgres
railway variables set OPENAI_API_KEY=sk-your-openai-api-key-here
railway variables set REDIS_URL='${{Redis.REDIS_URL}}'
railway variables set TEMP_DIR=/tmp/heimdex
```

**Note**: Worker doesn't need a public domain (it's an internal background service)

## Step 5: Deploy Frontend Service

```bash
# Go back to project root
cd /home/ljin/Projects/demo-heimdex-v3

# Create frontend service
railway service create frontend

# IMPORTANT: Frontend needs build arguments for Next.js
# We need to set these as variables first, then deploy
```

**Set Frontend environment variables:**
```bash
# Switch to frontend service
railway service --name frontend

# Set build-time variables (these are needed during Docker build)
railway variables set NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
railway variables set NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
railway variables set NEXT_PUBLIC_API_URL=https://your-api-domain.up.railway.app

# Note: Replace 'your-api-domain.up.railway.app' with the actual API domain from Step 3
```

**Deploy frontend:**
```bash
cd services/frontend
railway up --service frontend
```

**Generate public domain for frontend:**
```bash
railway domain

# This is your main application URL (e.g., https://frontend-production-xyz.up.railway.app)
```

## Step 6: Update CORS Configuration

Now that frontend has a domain, update the API's CORS settings:

```bash
# Switch to API service
railway service --name api

# Update CORS to include frontend domain
railway variables set API_CORS_ORIGINS=https://your-frontend-domain.up.railway.app

# Trigger redeployment
cd /home/ljin/Projects/demo-heimdex-v3/services/api
railway up --service api
```

## Step 7: Verify Deployment

**Check all services are running:**
```bash
# View project in browser
railway open

# Or check status for each service
railway service --name api
railway status

railway service --name worker
railway status

railway service --name frontend
railway status
```

**View logs:**
```bash
# API logs
railway service --name api
railway logs

# Worker logs
railway service --name worker
railway logs

# Frontend logs
railway service --name frontend
railway logs
```

## Step 8: Test the Application

1. **Get your frontend URL:**
   ```bash
   railway service --name frontend
   railway domain
   # Copy the public URL
   ```

2. **Visit the URL in your browser**
   - Landing page should load
   - Sign up / Log in
   - Upload a test video
   - Check worker logs to see processing
   - Test search functionality

## Quick Reference Commands

```bash
# List all services in project
railway service

# Switch between services
railway service --name <service-name>

# View environment variables
railway variables

# Set environment variable
railway variables set KEY=value

# Delete environment variable
railway variables delete KEY

# View logs (follow mode)
railway logs -f

# Redeploy current service
railway up

# Open Railway dashboard
railway open

# Get service domain
railway domain

# View project info
railway status
```

## Troubleshooting

### Issue: Service won't deploy

**Check logs:**
```bash
railway service --name <service-name>
railway logs
```

**Common issues:**
- Missing environment variables
- Incorrect Dockerfile path
- Build failures (check build logs)

### Issue: Frontend shows API errors

**Check:**
1. API service is running: `railway service --name api && railway status`
2. CORS is configured: `railway service --name api && railway variables | grep CORS`
3. Frontend has correct API URL: `railway service --name frontend && railway variables | grep API_URL`

### Issue: Videos not processing

**Check:**
1. Worker is running: `railway service --name worker && railway logs`
2. Redis connection: Check worker logs for connection errors
3. OpenAI API key is valid and has credits

## Environment Variables Checklist

### Redis (Database)
- ✅ Auto-configured by Railway
- ✅ `REDIS_URL` available to other services via `${{Redis.REDIS_URL}}`

### API Service
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_ANON_KEY`
- [ ] `SUPABASE_SERVICE_ROLE_KEY`
- [ ] `SUPABASE_JWT_SECRET`
- [ ] `DATABASE_URL`
- [ ] `OPENAI_API_KEY`
- [ ] `REDIS_URL` (reference: `${{Redis.REDIS_URL}}`)
- [ ] `API_CORS_ORIGINS` (update after frontend deployed)

### Worker Service
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_SERVICE_ROLE_KEY`
- [ ] `DATABASE_URL`
- [ ] `OPENAI_API_KEY`
- [ ] `REDIS_URL` (reference: `${{Redis.REDIS_URL}}`)
- [ ] `TEMP_DIR=/tmp/heimdex`

### Frontend Service
- [ ] `NEXT_PUBLIC_SUPABASE_URL`
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] `NEXT_PUBLIC_API_URL` (use API public domain)

## Cost Estimate

Railway pricing (as of 2025):
- **Hobby Plan**: $5/month + usage
- **Estimated monthly cost**: $20-35
  - Redis: ~$5
  - API: ~$5-10
  - Worker: ~$5-15
  - Frontend: ~$5

Plus OpenAI API costs: ~$20-50/month depending on usage

## Next Steps After Deployment

1. [ ] Set up custom domain (optional)
2. [ ] Configure monitoring/alerts
3. [ ] Set up error tracking (Sentry)
4. [ ] Configure database backups
5. [ ] Review and optimize costs
6. [ ] Document deployment in DEVLOG

---

**Deployment completed!** 🎉

Your Heimdex application should now be live on Railway.

Frontend URL: `https://your-frontend-domain.up.railway.app`
