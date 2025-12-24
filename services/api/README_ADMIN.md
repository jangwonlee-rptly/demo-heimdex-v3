# Heimdex Admin Metrics - Complete Guide

## Overview

The admin metrics feature provides business intelligence and user analytics through secure, backend-enforced admin-only endpoints.

**What it does:**
- Tracks video processing metrics (volume, success rate, hours processed)
- Monitors search activity and performance
- Provides per-user usage analytics
- Supports user drilldown with recent activity

**Security:**
- Admin access controlled by environment variable allowlist (`ADMIN_USER_IDS`)
- Backend enforcement via `require_admin()` dependency
- Returns 403 Forbidden for non-admin users
- Works with existing Supabase JWT authentication

## Quick Start

**1. Apply database migration:**
```bash
psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql
```

**2. Configure admin user:**
```bash
# Get your user ID from browser console after logging in:
# (await supabase.auth.getSession()).data.session?.user?.id

# Add to services/api/.env:
echo "ADMIN_USER_IDS=799f1283-a2d7-4f8a-96e6-faf71a749b64" >> .env
```

**3. Verify configuration:**
```bash
cd services/api
python3 verify_admin_config.py
```

**4. Restart API and test:**
```bash
uvicorn src.main:app --reload
# Navigate to http://localhost:3000/admin
```

See `QUICKSTART_ADMIN.md` for detailed step-by-step instructions.

## Architecture

### Backend Components

**Admin Router** (`src/routes/admin.py`)
- 5 endpoints under `/v1/admin/*`
- All require `require_admin()` dependency
- Returns structured JSON responses

**Admin Middleware** (`src/auth/middleware.py`)
- `require_admin(user: User) -> User` dependency
- Checks `user.user_id in settings.admin_user_ids_list`
- Raises 403 if not authorized

**Database Adapter** (`src/adapters/database.py`)
- Methods call PostgreSQL RPC functions
- Efficient SQL aggregation
- Uses existing schema (no new tables)

**RPC Functions** (`infra/migrations/018_add_admin_metrics_rpc_functions.sql`)
- `get_admin_overview_metrics()` - System KPIs
- `get_throughput_timeseries(days_back)` - Daily video processing
- `get_search_timeseries(days_back)` - Daily search volume
- `get_admin_users_list(...)` - Paginated user list
- `get_admin_user_detail(user_id, days_back)` - User drilldown

### Frontend Components

**Admin Dashboard** (`frontend/src/app/admin/page.tsx`)
- KPI cards (4 metrics)
- Time series charts (throughput + search)
- Sortable users table
- Client-side routing to user detail

**User Detail Page** (`frontend/src/app/admin/users/[id]/page.tsx`)
- User summary metrics
- Recent videos table
- Recent searches table
- Back navigation

## API Reference

### Authentication

All endpoints require JWT bearer token in Authorization header:

```bash
curl -H "Authorization: Bearer <jwt-token>" \
  http://localhost:8000/v1/admin/overview
```

User's ID (from JWT `sub` claim) must be in `ADMIN_USER_IDS` allowlist.

### Endpoints

#### GET /v1/admin/overview

Returns system-wide KPIs.

**Response:**
```json
{
  "videos_ready_total": 1234,
  "videos_failed_total": 56,
  "videos_total": 1290,
  "failure_rate_pct": 4.34,
  "hours_ready_total": 156.7,
  "searches_7d": 2345,
  "avg_search_latency_ms_7d": 123.4,
  "searches_30d": 8901,
  "avg_search_latency_ms_30d": 145.2
}
```

#### GET /v1/admin/timeseries/throughput

Daily video processing metrics.

**Query Parameters:**
- `range`: Time window (e.g., "7d", "30d", "90d")
- `bucket`: Aggregation bucket ("day" only in Phase 1)

**Example:**
```bash
GET /v1/admin/timeseries/throughput?range=30d&bucket=day
```

**Response:**
```json
{
  "data": [
    {"day": "2025-12-01", "videos_ready": 45, "hours_ready": 5.6},
    {"day": "2025-12-02", "videos_ready": 52, "hours_ready": 6.2}
  ]
}
```

#### GET /v1/admin/timeseries/search

Daily search activity metrics.

**Query Parameters:**
- `range`: Time window (e.g., "7d", "30d", "90d")
- `bucket`: Aggregation bucket ("day" only)

**Example:**
```bash
GET /v1/admin/timeseries/search?range=30d&bucket=day
```

**Response:**
```json
{
  "data": [
    {"day": "2025-12-01", "searches": 234, "avg_latency_ms": 125.3},
    {"day": "2025-12-02", "searches": 198, "avg_latency_ms": 132.1}
  ]
}
```

#### GET /v1/admin/users

Paginated user list with usage metrics.

**Query Parameters:**
- `range`: Time window for recent metrics (default: "7d")
- `page`: Page number, 1-indexed (default: 1)
- `page_size`: Items per page, max 100 (default: 50)
- `sort`: Sort column (default: "last_activity")
  - `last_activity` - Most recent first
  - `hours_ready` - Most hours first
  - `videos_ready` - Most videos first
  - `searches_7d` - Most searches first

**Example:**
```bash
GET /v1/admin/users?range=7d&page=1&page_size=50&sort=hours_ready
```

**Response:**
```json
{
  "items": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "full_name": "Alice Johnson",
      "videos_total": 45,
      "videos_ready": 42,
      "hours_ready": 12.5,
      "last_activity": "2025-12-23T10:30:00Z",
      "searches_7d": 123,
      "avg_latency_ms_7d": 145.2
    }
  ],
  "page": 1,
  "page_size": 50,
  "total_users": null
}
```

#### GET /v1/admin/users/{user_id}

User drilldown with recent activity.

**Path Parameters:**
- `user_id`: User UUID

**Example:**
```bash
GET /v1/admin/users/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "Alice Johnson",
  "videos_total": 45,
  "videos_ready": 42,
  "hours_ready": 12.5,
  "last_activity": "2025-12-23T10:30:00Z",
  "searches_7d": 123,
  "avg_latency_ms_7d": 145.2,
  "recent_videos": [
    {
      "id": "uuid",
      "filename": "video.mp4",
      "status": "READY",
      "duration_s": 120.5,
      "updated_at": "2025-12-23T10:00:00Z",
      "error_message": null
    }
  ],
  "recent_searches": [
    {
      "query_text": "walking in park",
      "created_at": "2025-12-23T09:00:00Z",
      "latency_ms": 145,
      "results_count": 12,
      "video_id": "uuid"
    }
  ]
}
```

## Configuration

### Environment Variables

**ADMIN_USER_IDS** (required for admin access)

Comma-separated list of user UUIDs with admin privileges.

```bash
# Single admin
ADMIN_USER_IDS=799f1283-a2d7-4f8a-96e6-faf71a749b64

# Multiple admins
ADMIN_USER_IDS=uuid1,uuid2,uuid3
```

**How to get user IDs:**

Method 1 - Browser console (user is logged in):
```javascript
(await supabase.auth.getSession()).data.session?.user?.id
```

Method 2 - Supabase dashboard:
1. Go to Authentication → Users
2. Find user in table
3. Copy UUID

Method 3 - SQL query:
```sql
SELECT id, email FROM auth.users WHERE email = 'admin@example.com';
```

### Verification

**Check configuration loaded correctly:**

```bash
cd services/api
python3 verify_admin_config.py
```

Expected output:
```
========================================
Heimdex Admin Configuration Verification
========================================

1. Raw ADMIN_USER_IDS value:
   '799f1283-a2d7-4f8a-96e6-faf71a749b64'

2. Parsed admin user IDs list:
   [1] 799f1283-a2d7-4f8a-96e6-faf71a749b64

3. Configuration Status:
   ✅ 1 admin user(s) configured
```

## Testing

### Manual Testing

**1. Test admin access:**
```bash
# Log in as admin user
# Navigate to http://localhost:3000/admin
# Should see dashboard with metrics
```

**2. Test non-admin access:**
```bash
# Log in as different user (not in ADMIN_USER_IDS)
# Navigate to http://localhost:3000/admin
# Should see "Access Denied" error
```

**3. Test API directly:**
```bash
# Get JWT token from browser Network tab
TOKEN="your-token"

# Should return 200 OK with metrics
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/overview

# Non-admin should return 403 Forbidden
curl -H "Authorization: Bearer $NON_ADMIN_TOKEN" \
  http://localhost:8000/v1/admin/overview
```

### Automated Testing

See `ADMIN_METRICS_PHASE1_SUMMARY.md` for complete test plan with 7 test scenarios.

## Deployment

### Local Development

1. Apply migration to local database
2. Set `ADMIN_USER_IDS` in `services/api/.env`
3. Restart API: `uvicorn src.main:app --reload`
4. Test at http://localhost:3000/admin

### Production (Railway + Supabase)

**Database (Supabase):**
1. Go to SQL Editor
2. Paste migration 018 content
3. Run (one-time)

**API (Railway):**
1. Go to project → api service → Variables
2. Add `ADMIN_USER_IDS` with production user UUIDs
3. Save (auto-redeploys)

**Frontend (Vercel/Railway):**
- No changes needed
- `/admin` routes work automatically

## Troubleshooting

### Issue: "Access Denied" for admin user

**Cause:** User ID mismatch

**Debug:**
1. Get user ID from browser: `(await supabase.auth.getSession()).data.session?.user?.id`
2. Check it matches `ADMIN_USER_IDS` exactly
3. Verify config loaded: `python3 verify_admin_config.py`
4. Check API logs for "Non-admin user attempted to access admin endpoint"

### Issue: Empty metrics (all zeros)

**Cause:** No data in database yet

**Expected:** Normal for new deployments

**To populate:**
1. Upload videos
2. Wait for processing
3. Perform searches
4. Metrics will update

### Issue: RPC function errors

**Cause:** Migration not applied

**Fix:**
```bash
# Check functions exist
psql $DATABASE_URL -c "SELECT routine_name FROM information_schema.routines WHERE routine_name LIKE 'get_admin%';"

# Should show 5 functions
# If not, apply migration:
psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql
```

### Issue: Config shows empty admin_user_ids

**Debug:**
```bash
cd services/api
python3 -c "from src.config import settings; print(repr(settings.admin_user_ids))"
```

**If shows empty string:**
1. Check `.env` file exists: `ls -la services/api/.env`
2. Check variable set: `grep ADMIN_USER_IDS services/api/.env`
3. No extra quotes: `ADMIN_USER_IDS=uuid` not `ADMIN_USER_IDS="uuid"`
4. Restart API after editing `.env`

## Phase 1 Limitations

These are known limitations to be addressed in Phase 2:

1. **Approximate completion time:** Uses `videos.updated_at` as proxy
2. **No RTF metrics:** Requires processing duration timestamps
3. **No per-stage failures:** Only overall failure rate
4. **No storage metrics:** File sizes not tracked
5. **Text-based charts:** Can enhance with Chart.js/Recharts
6. **No pagination totals:** Minor optimization

All metrics are computed from existing schema - no new columns required.

## Security Considerations

**Access Control:**
- Admin endpoints protected by backend middleware
- Frontend checks are for UX only (not security)
- JWT must be valid AND user ID in allowlist

**RPC Functions:**
- Use `SECURITY DEFINER` to run with elevated privileges
- No SQL injection risk (parameterized queries)
- Return aggregated data only (no raw PII exposure)

**Best Practices:**
- Use UUIDs from trusted source (Supabase auth)
- Rotate admin access by updating `ADMIN_USER_IDS`
- Monitor admin endpoint usage in logs
- Restrict admin access to minimal set of users

## Files Reference

**Backend:**
- `src/routes/admin.py` - Admin endpoints
- `src/auth/middleware.py` - `require_admin()` dependency
- `src/adapters/database.py` - Admin metrics methods
- `src/domain/admin_schemas.py` - Pydantic models
- `src/config.py` - `ADMIN_USER_IDS` configuration

**Frontend:**
- `frontend/src/app/admin/page.tsx` - Dashboard
- `frontend/src/app/admin/users/[id]/page.tsx` - User detail

**Database:**
- `infra/migrations/018_add_admin_metrics_rpc_functions.sql` - RPC functions

**Documentation:**
- `README_ADMIN.md` - This file (complete reference)
- `QUICKSTART_ADMIN.md` - Quick start guide
- `ADMIN_METRICS_SETUP.md` - Detailed setup guide
- `ADMIN_METRICS_PHASE1_SUMMARY.md` - Implementation summary

**Tools:**
- `verify_admin_config.py` - Configuration verification script

## Support

**Common Questions:**

Q: How do I add a new admin user?
A: Add their UUID to `ADMIN_USER_IDS` (comma-separated), restart API

Q: Can I remove admin access?
A: Yes, remove UUID from `ADMIN_USER_IDS`, restart API

Q: Do I need to apply migration multiple times?
A: No, only once per database (local + production separately)

Q: Why do charts show "No data available"?
A: Normal for new deployments - upload videos and perform searches to populate

Q: Can regular users see any admin data?
A: No, all admin endpoints return 403 for non-admin users

**Need Help?**
1. Run `python3 verify_admin_config.py` to check setup
2. Check API logs for error messages
3. Review troubleshooting section above
4. See detailed guides in documentation files
