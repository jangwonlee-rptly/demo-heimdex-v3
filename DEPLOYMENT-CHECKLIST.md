# Heimdex Deployment Checklist

Use this checklist when deploying Heimdex to production.

## Pre-Deployment

### Local Verification
- [ ] Run `./scripts/pre-deploy-check.sh` - all checks pass
- [ ] Run `./scripts/verify-env.sh` - all env vars set
- [ ] Run `docker-compose build` - all services build successfully
- [ ] Run `docker-compose up` - all services start without errors
- [ ] Test locally: upload video, verify processing, test search
- [ ] All GitHub Actions CI/CD checks pass

### Supabase Setup
- [ ] Supabase project created
- [ ] Migration `001_initial_schema.sql` executed
- [ ] Migration `002_enable_pgvector.sql` executed
- [ ] Storage bucket created (default: videos)
- [ ] RLS policies reviewed and enabled
- [ ] Database credentials saved securely
- [ ] API keys saved securely (anon key, service role key, JWT secret)

### External Services
- [ ] OpenAI API key created
- [ ] OpenAI account has sufficient credits ($10+ recommended)
- [ ] GitHub repository created
- [ ] Code pushed to GitHub (main branch)
- [ ] Custom domain DNS ready (if applicable)

### Documentation
- [ ] `.env.example` updated with all required variables
- [ ] `README.md` is current
- [ ] `DEPLOYMENT.md` reviewed
- [ ] Team has access to deployment guide

## Deployment (Railway Example)

### Platform Setup
- [ ] Railway account created
- [ ] GitHub connected to Railway
- [ ] New project created from repository
- [ ] Billing information added (if needed)

### Service Configuration

#### Redis
- [ ] Redis service added
- [ ] Connection URL noted (`REDIS_URL`)

#### API Service
- [ ] Service detected or manually added
- [ ] Root directory: `services/api`
- [ ] Environment variables added:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_ANON_KEY`
  - [ ] `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] `SUPABASE_JWT_SECRET`
  - [ ] `DATABASE_URL`
  - [ ] `OPENAI_API_KEY`
  - [ ] `REDIS_URL` (reference to Redis service)
  - [ ] `API_CORS_ORIGINS` (frontend domain)
- [ ] Public networking enabled
- [ ] Public URL noted

#### Worker Service
- [ ] Service detected or manually added
- [ ] Root directory: `services/worker`
- [ ] Environment variables added:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] `DATABASE_URL`
  - [ ] `OPENAI_API_KEY`
  - [ ] `REDIS_URL` (reference to Redis service)
  - [ ] `TEMP_DIR=/tmp/heimdex`
- [ ] No public networking needed

#### Frontend Service
- [ ] Service detected or manually added
- [ ] Root directory: `services/frontend`
- [ ] Build arguments added (IMPORTANT):
  - [ ] `NEXT_PUBLIC_SUPABASE_URL`
  - [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - [ ] `NEXT_PUBLIC_API_URL` (API public URL)
- [ ] Environment variables added (same as build args)
- [ ] Public networking enabled
- [ ] Public URL noted

### Deploy
- [ ] Initial deployment triggered
- [ ] All services deploy successfully
- [ ] No errors in deployment logs

## Post-Deployment

### Verification
- [ ] Frontend loads at public URL
- [ ] Landing page renders correctly
- [ ] Sign up creates new user
- [ ] Login works with test account
- [ ] Upload video succeeds
- [ ] Check worker logs - processing started
- [ ] Processing completes successfully
- [ ] Search finds the uploaded video
- [ ] Video playback works
- [ ] All pages load without errors

### Configuration
- [ ] Update `API_CORS_ORIGINS` with actual frontend domain
- [ ] Redeploy API with updated CORS
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificate active (automatic on Railway/Render)
- [ ] DNS propagation verified

### Monitoring Setup
- [ ] Error tracking configured (Sentry recommended)
- [ ] Uptime monitoring configured (Better Uptime recommended)
- [ ] Log aggregation setup (optional)
- [ ] Alerts configured:
  - [ ] API downtime alert
  - [ ] Worker failure alert
  - [ ] Database connection alert
  - [ ] High error rate alert

### Documentation
- [ ] Deployment URLs documented
- [ ] Admin credentials saved securely
- [ ] Runbook created for common issues
- [ ] Team notified of deployment
- [ ] Deployment notes added to DEVLOG

### Backup & Recovery
- [ ] Database backup verified (Supabase automatic backups)
- [ ] Manual backup process documented
- [ ] Rollback plan tested
- [ ] Disaster recovery plan documented

## Production Hardening (Week 1)

### Security
- [ ] Review all environment variables - no secrets exposed
- [ ] Supabase RLS policies tested
- [ ] CORS properly restricted (no wildcards)
- [ ] Rate limiting considered (if high traffic expected)
- [ ] API authentication verified
- [ ] 2FA enabled on all service accounts

### Performance
- [ ] API response times measured (< 200ms target)
- [ ] Frontend load times measured (< 2s target)
- [ ] Worker processing times measured
- [ ] Bottlenecks identified
- [ ] Caching strategy reviewed

### Monitoring
- [ ] Week 1 metrics reviewed
- [ ] Error rate acceptable (< 1%)
- [ ] Resource usage within limits
- [ ] Costs within budget
- [ ] User feedback collected

## Scaling (As Needed)

### When to Scale
- [ ] CPU > 70% sustained
- [ ] Memory > 80% sustained
- [ ] Worker queue backlog growing
- [ ] API response times > 500ms
- [ ] User count growing significantly

### How to Scale
- [ ] Increase worker instances (priority 1)
- [ ] Increase API resources (if needed)
- [ ] Increase frontend resources (last priority)
- [ ] Consider caching layer (Redis)
- [ ] Consider CDN for video delivery

## Maintenance Schedule

### Daily
- [ ] Check error logs
- [ ] Monitor uptime
- [ ] Verify worker is processing videos

### Weekly
- [ ] Review metrics and costs
- [ ] Check for dependency updates
- [ ] Review user feedback
- [ ] Database size check

### Monthly
- [ ] Security audit
- [ ] Performance review
- [ ] Cost optimization review
- [ ] Backup restoration test
- [ ] Disaster recovery drill

## Emergency Contacts

- **Deployment Platform**: [Railway/Render support]
- **Supabase Support**: https://supabase.com/dashboard/support
- **OpenAI Support**: https://help.openai.com
- **On-Call Engineer**: [Your contact]

## Useful Commands

### Check deployment status
```bash
# Railway
railway status

# Render
# Check dashboard

# DigitalOcean
doctl apps list
```

### View logs
```bash
# Railway
railway logs --service api
railway logs --service worker

# Render
# Use dashboard or CLI
```

### Rollback deployment
```bash
# Railway - use dashboard
# Render - use dashboard
```

### Connect to database
```bash
# Supabase
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"
```

### Check Redis
```bash
# Railway - use dashboard to get connection details
redis-cli -u $REDIS_URL
> PING
> INFO
```

---

**Deployment Completed**: ____/____/________
**Deployed By**: ________________
**Platform**: ________________
**Version**: ________________
**Notes**:
