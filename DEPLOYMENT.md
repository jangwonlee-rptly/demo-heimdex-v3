# Heimdex Deployment Guide

**Goal**: Simple, efficient, and foolproof deployment strategy for Heimdex.

## Table of Contents
1. [Recommended Approach: Railway.app](#option-1-railwayapp-recommended)
2. [Alternative: Render.com](#option-2-rendercom-alternative)
3. [Alternative: DigitalOcean App Platform](#option-3-digitalocean-app-platform)
4. [Alternative: Fly.io](#option-4-flyio)
5. [Pre-Deployment Checklist](#pre-deployment-checklist)
6. [Post-Deployment Tasks](#post-deployment-tasks)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Rollback Strategy](#rollback-strategy)

---

## Platform Comparison

| Platform | Ease of Setup | Docker Support | Cost (Est/mo) | Managed Redis | Auto Deploy | Best For |
|----------|---------------|----------------|---------------|---------------|-------------|----------|
| **Railway** ⭐ | ⭐⭐⭐⭐⭐ | Native | $15-30 | ✅ | ✅ | Production-ready apps |
| **Render** | ⭐⭐⭐⭐ | Good | $7-25 (Free tier) | ✅ | ✅ | MVP/Demo |
| **DigitalOcean** | ⭐⭐⭐ | Good | $12-30 | ✅ | ✅ | Predictable pricing |
| **Fly.io** | ⭐⭐⭐ | Excellent | $10-25 | ✅ | ✅ | Global edge apps |

---

## Option 1: Railway.app (RECOMMENDED)

**Why Railway?**
- ✅ Native Docker Compose support
- ✅ Automatic GitHub deployments
- ✅ Managed Redis included
- ✅ Simple environment variable management
- ✅ Built-in monitoring and logs
- ✅ One-click rollbacks
- ✅ Best developer experience

**Estimated Cost**: $15-30/month

### Step 1: Prepare Your Project

1. **Ensure your code is pushed to GitHub** (you already have this)
2. **Verify environment variables** in `.env.example`
3. **Test Docker build locally**:
   ```bash
   docker-compose build
   docker-compose up
   ```

### Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your `demo-heimdex-v3` repository
6. Railway will automatically detect your `docker-compose.yml`

### Step 3: Configure Services

Railway will create services based on your docker-compose.yml. You need to configure each:

#### 3a. Add Redis Service First

1. In Railway dashboard, click "+ New"
2. Select "Database" → "Redis"
3. Note the connection URL (automatically available as `REDIS_URL`)

#### 3b. Configure API Service

1. Select the `api` service
2. Add environment variables:
   ```
   SUPABASE_URL=<your-supabase-url>
   SUPABASE_ANON_KEY=<your-supabase-anon-key>
   SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
   SUPABASE_JWT_SECRET=<your-jwt-secret>
   DATABASE_URL=<your-supabase-database-url>
   OPENAI_API_KEY=<your-openai-key>
   REDIS_URL=${{Redis.REDIS_URL}}
   API_CORS_ORIGINS=https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}
   ```
3. Under "Settings" → "Networking":
   - Enable "Public Networking"
   - Note the public URL (e.g., `https://api-production-abc123.up.railway.app`)

#### 3c. Configure Worker Service

1. Select the `worker` service
2. Add environment variables:
   ```
   SUPABASE_URL=<your-supabase-url>
   SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
   DATABASE_URL=<your-supabase-database-url>
   OPENAI_API_KEY=<your-openai-key>
   REDIS_URL=${{Redis.REDIS_URL}}
   TEMP_DIR=/tmp/heimdex
   ```
3. No public networking needed (internal service only)

#### 3d. Configure Frontend Service

1. Select the `frontend` service
2. Add environment variables (including build-time vars):
   ```
   NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
   NEXT_PUBLIC_API_URL=https://<your-api-railway-url>
   ```
3. Under "Settings" → "Networking":
   - Enable "Public Networking"
   - This is your main application URL
4. **IMPORTANT**: Add these as build arguments in Railway:
   - Settings → "Build" → "Docker Build Arguments"
   - Add each `NEXT_PUBLIC_*` variable

### Step 4: Deploy

1. Railway automatically deploys on git push to `main`
2. Monitor deployment logs in Railway dashboard
3. Services will start in order: Redis → API → Worker → Frontend

### Step 5: Verify Deployment

1. Visit your Frontend URL: `https://frontend-production-xyz.up.railway.app`
2. Test the landing page
3. Sign up / Log in
4. Upload a test video
5. Check worker logs to confirm processing
6. Test search functionality

### Step 6: Custom Domain (Optional)

1. In Frontend service → Settings → Domains
2. Add your custom domain (e.g., `app.heimdex.com`)
3. Update DNS records as instructed
4. Update `NEXT_PUBLIC_API_URL` if you add custom domain to API

---

## Option 2: Render.com (ALTERNATIVE)

**Why Render?**
- ✅ Free tier available (with limitations)
- ✅ Docker support
- ✅ Managed Redis
- ⚠️ Slower deploys than Railway
- ⚠️ Free tier has cold starts (services sleep after 15 min inactivity)

**Estimated Cost**: Free tier or $7-25/month

### Quick Start

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Create a "New Blueprint" or manually add services:

#### Create Services

1. **Redis**:
   - New → Redis
   - Free tier or $7/month
   - Note the Internal Redis URL

2. **API Service**:
   - New → Web Service
   - Connect GitHub repo
   - Root Directory: `services/api`
   - Environment: Docker
   - Add environment variables (same as Railway)
   - Plan: Starter ($7/mo) or higher

3. **Worker Service**:
   - New → Background Worker
   - Connect GitHub repo
   - Root Directory: `services/worker`
   - Environment: Docker
   - Add environment variables

4. **Frontend Service**:
   - New → Web Service
   - Connect GitHub repo
   - Root Directory: `services/frontend`
   - Environment: Docker
   - Add build-time env vars
   - Plan: Starter ($7/mo) or higher

**Total Cost on Render**: ~$21/month (or Free tier with limitations)

---

## Option 3: DigitalOcean App Platform

**Why DigitalOcean?**
- ✅ Predictable pricing
- ✅ Docker support
- ✅ Good documentation
- ⚠️ More manual configuration

**Estimated Cost**: $12-30/month

### Quick Start

1. Go to [DigitalOcean App Platform](https://www.digitalocean.com/products/app-platform)
2. Create new app from GitHub
3. Add components:
   - Frontend (Web Service)
   - API (Web Service)
   - Worker (Worker)
   - Redis (Managed Database - $15/mo minimum)

4. Configure environment variables for each component
5. Deploy

---

## Option 4: Fly.io

**Why Fly.io?**
- ✅ Excellent Docker support
- ✅ Global edge deployment
- ✅ Good free tier
- ⚠️ Requires fly.toml configuration files

**Estimated Cost**: $10-25/month

### Setup Required

You'll need to create `fly.toml` files for each service. Fly.io is command-line focused.

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Create apps for each service
4. Configure and deploy

This option requires more technical setup but offers great performance.

---

## Pre-Deployment Checklist

Before deploying to any platform:

- [ ] **Code is pushed to GitHub** (main branch)
- [ ] **Supabase project is set up**
  - [ ] Migrations are run (001_initial_schema.sql, 002_enable_pgvector.sql)
  - [ ] Storage bucket exists
  - [ ] RLS policies are configured
- [ ] **OpenAI API key is ready** (with credits)
- [ ] **Environment variables documented** (use .env.example as reference)
- [ ] **Docker builds work locally**:
  ```bash
  docker-compose build
  docker-compose up
  # Test: Upload video, verify processing, test search
  ```
- [ ] **CI/CD pipeline passes** (GitHub Actions)
- [ ] **Update CORS settings** for production domains
- [ ] **Prepare custom domains** (if applicable)

---

## Post-Deployment Tasks

After successful deployment:

### 1. Update Frontend Environment Variables

If your API URL changes, update:
```
NEXT_PUBLIC_API_URL=https://your-api-domain.com
```

Rebuild and redeploy frontend.

### 2. Configure CORS

Update API environment variable:
```
API_CORS_ORIGINS=https://your-frontend-domain.com,https://www.your-domain.com
```

### 3. Test Critical Paths

- [ ] Landing page loads
- [ ] Sign up / Log in works
- [ ] Video upload succeeds
- [ ] Video processing completes (check worker logs)
- [ ] Search returns results
- [ ] Video playback works

### 4. Set Up Monitoring

**Railway**: Built-in metrics and logs
**Render**: Built-in monitoring
**DigitalOcean**: Built-in insights

Additional recommendations:
- **Sentry** for error tracking (free tier): https://sentry.io
- **Better Uptime** for uptime monitoring (free tier): https://betterstack.com/uptime
- **LogTail** for log aggregation: https://logtail.com

### 5. Database Backups

Supabase provides automatic daily backups on paid plans ($25/mo).

**Manual backup**:
```bash
# From Supabase dashboard: Database → Backups
# Or use pg_dump:
pg_dump -h db.your-project.supabase.co -U postgres -d postgres > backup.sql
```

### 6. Set Up Alerts

Configure alerts for:
- API/Frontend downtime
- Worker queue buildup (Redis queue depth)
- Database connection errors
- OpenAI API quota exceeded

---

## Monitoring & Maintenance

### Key Metrics to Track

1. **Application Health**
   - API response time (< 200ms ideal)
   - Frontend load time (< 2s ideal)
   - Worker processing time per video

2. **Infrastructure**
   - CPU usage (< 70% sustained)
   - Memory usage (< 80%)
   - Redis memory usage
   - Database connections

3. **Business Metrics**
   - Videos uploaded per day
   - Search queries per day
   - Average processing time
   - Error rate (< 1%)

### Log Monitoring

**Important logs to watch**:
- API errors (HTTP 500s)
- Worker failures (job retries, crashes)
- Database connection errors
- OpenAI API errors (rate limits, quota)

**Railway**: Logs are in each service dashboard
**Render**: Logs tab in each service

### Cost Monitoring

**Railway**: Dashboard shows current usage and projected costs
**Render**: Billing page shows usage

**Typical monthly costs** (Railway):
- Redis: $5
- API (512MB): $5-10
- Worker (512MB-1GB): $5-15
- Frontend (512MB): $5
- **Total**: ~$20-35/month

---

## Scaling Strategy

### When to Scale

Scale when:
- CPU consistently > 70%
- Memory consistently > 80%
- Worker queue backlog growing
- API response time > 500ms
- User count growing significantly

### How to Scale

#### Vertical Scaling (Increase resources)
- Railway: Settings → Resources → Increase RAM/CPU
- Render: Upgrade plan

#### Horizontal Scaling (Add more instances)
- Add more worker instances for faster video processing
- API can handle moderate traffic with 1 instance
- Frontend is stateless, can scale easily

### Scaling Priority
1. **Worker** - Most resource intensive (FFmpeg, OpenAI calls)
2. **API** - Only if seeing response time issues
3. **Frontend** - Last priority (static serving is cheap)

---

## Rollback Strategy

### Railway Rollback

1. Go to service → Deployments
2. Find last working deployment
3. Click "Redeploy"
4. Deployment rolls back in ~2 minutes

### Render Rollback

1. Go to service → Deploys
2. Find successful deploy
3. Click "Rollback to this version"

### Database Rollback

**⚠️ CRITICAL: Database rollbacks are destructive**

If you need to rollback a migration:
1. Restore from Supabase backup
2. Or manually run down migration scripts

**Prevention**: Test migrations in staging environment first

### Emergency Rollback

If production is completely broken:

1. **Rollback code** using platform UI
2. **Check worker queue**: Clear stuck jobs if needed
   ```bash
   # Connect to Redis and clear queue
   redis-cli -u $REDIS_URL
   > FLUSHALL
   ```
3. **Verify database** is accessible
4. **Check external services** (Supabase, OpenAI)
5. **Monitor logs** after rollback

---

## Troubleshooting Common Issues

### Issue: Frontend shows "API Error"

**Check**:
1. API service is running (check Railway/Render dashboard)
2. `NEXT_PUBLIC_API_URL` is correct
3. CORS is configured correctly
4. API logs for errors

**Fix**:
- Rebuild frontend with correct API URL
- Update API CORS settings

### Issue: Videos not processing

**Check**:
1. Worker service is running
2. Redis connection is healthy
3. Worker logs for errors
4. OpenAI API key is valid and has credits
5. Supabase storage permissions

**Fix**:
- Restart worker service
- Check OPENAI_API_KEY environment variable
- Verify Supabase service role key permissions

### Issue: Search returns no results

**Check**:
1. pgvector extension is enabled (002_enable_pgvector.sql)
2. Video scenes were created (check database)
3. OpenAI embeddings were generated
4. Search query logs for errors

**Fix**:
- Re-run pgvector migration
- Re-process videos to regenerate embeddings

### Issue: High costs

**Check**:
1. OpenAI API usage (most expensive component)
2. Worker processing too many videos
3. Resources over-provisioned

**Fix**:
- Monitor OpenAI costs in OpenAI dashboard
- Reduce worker concurrency
- Right-size resources

---

## Cost Optimization Tips

1. **OpenAI API** (Biggest cost driver):
   - Use GPT-4o-mini for visual analysis instead of GPT-4o
   - Limit scene detection sensitivity (fewer scenes = fewer API calls)
   - Cache embeddings aggressively

2. **Infrastructure**:
   - Start small (512MB instances)
   - Scale only when needed
   - Use free tiers for staging environments

3. **Supabase**:
   - Free tier: 500MB database, 1GB storage
   - Paid tier: $25/mo for backups and more resources
   - Use Supabase storage (free up to 1GB)

4. **Video Storage**:
   - Compress videos before upload (client-side)
   - Delete old videos if not needed
   - Use Supabase storage (cheaper than S3)

---

## Security Best Practices

- [ ] **Never commit `.env` file** (already gitignored ✅)
- [ ] **Use environment variables** for all secrets
- [ ] **Rotate API keys** periodically
- [ ] **Enable HTTPS** (automatic on Railway/Render)
- [ ] **Configure CORS properly** (don't use `*`)
- [ ] **Review Supabase RLS policies** (ensure users can only access their data)
- [ ] **Monitor for suspicious activity** (unusual API usage)
- [ ] **Keep dependencies updated** (run `npm audit`, `pip-audit`)
- [ ] **Use service role key sparingly** (only in backend)
- [ ] **Enable 2FA** on all service accounts (GitHub, Railway, Supabase, OpenAI)

---

## Recommended Deployment Path

For your use case (demo/MVP that needs to be production-ready), here's my recommendation:

### Phase 1: Initial Deployment (Railway)
1. Deploy to Railway.app using steps above
2. Test thoroughly with real users
3. Monitor costs and performance
4. **Total time**: 1-2 hours
5. **Cost**: ~$20-30/month

### Phase 2: Production Hardening (Week 1-2)
1. Add custom domain
2. Set up Sentry for error tracking
3. Configure uptime monitoring
4. Set up database backup schedule
5. Document runbooks for common issues

### Phase 3: Optimization (Month 1-2)
1. Monitor costs and optimize
2. Scale resources based on actual usage
3. Improve caching and performance
4. Consider CDN for video delivery

### Phase 4: Scale (As needed)
1. Add more worker instances if needed
2. Consider moving to DigitalOcean or AWS for enterprise features
3. Implement advanced monitoring (DataDog, New Relic)

---

## Next Steps

**Ready to deploy? Start here:**

1. [ ] Review this deployment guide
2. [ ] Choose a platform (Railway recommended)
3. [ ] Complete pre-deployment checklist
4. [ ] Follow platform-specific steps above
5. [ ] Test deployment thoroughly
6. [ ] Set up monitoring
7. [ ] Celebrate! 🎉

**Questions or issues?**
- Railway docs: https://docs.railway.app
- Render docs: https://render.com/docs
- Supabase docs: https://supabase.com/docs

---

**Last Updated**: 2025-11-17
**Maintained by**: Heimdex Team
