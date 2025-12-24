# Heimdex Admin Metrics - Phase 1 Setup Guide

## Overview

Phase 1 implements admin-only metrics dashboard with backend security, using existing database schema (no migrations required in Phase 1, except for RPC functions).

## New Environment Variables

Add to `services/api/.env`:

```bash
# Admin Configuration
ADMIN_USER_IDS=uuid1,uuid2,uuid3  # Comma-separated UUIDs of admin users
```

**Example:**
```bash
ADMIN_USER_IDS=550e8400-e29b-41d4-a716-446655440000,6ba7b810-9dad-11d1-80b4-00c04fd430c8
```

To get your user ID:
1. Log in to Heimdex frontend
2. Open browser console
3. Run: `(await supabase.auth.getSession()).data.session?.user?.id`

## Database Setup

### Required Migration

Run the SQL migration to create admin RPC functions:

```bash
# Apply migration 018
psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql
```

Or in Supabase dashboard:
1. Go to SQL Editor
2. Paste contents of `infra/migrations/018_add_admin_metrics_rpc_functions.sql`
3. Run

This creates 5 PostgreSQL functions:
- `get_admin_overview_metrics()` - KPI totals
- `get_throughput_timeseries(days_back)` - Daily video processing
- `get_search_timeseries(days_back)` - Daily search volume
- `get_admin_users_list(...)` - Paginated user list with sorting
- `get_admin_user_detail(user_id, days_back)` - User drilldown

All functions use `SECURITY DEFINER` to run with elevated privileges.

## API Endpoints

All endpoints require `Authorization: Bearer <jwt>` header and admin user ID in allowlist.

### 1. GET /v1/admin/overview

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

### 2. GET /v1/admin/timeseries/throughput?range=30d&bucket=day

**Query Parameters:**
- `range`: Time range (e.g., "30d", "7d", "90d")
- `bucket`: Time bucket ("day" only in Phase 1)

**Response:**
```json
{
  "data": [
    {
      "day": "2025-12-01",
      "videos_ready": 45,
      "hours_ready": 5.6
    },
    {
      "day": "2025-12-02",
      "videos_ready": 52,
      "hours_ready": 6.2
    }
  ]
}
```

### 3. GET /v1/admin/timeseries/search?range=30d&bucket=day

**Query Parameters:**
- `range`: Time range (e.g., "30d", "7d", "90d")
- `bucket`: Time bucket ("day" only in Phase 1)

**Response:**
```json
{
  "data": [
    {
      "day": "2025-12-01",
      "searches": 234,
      "avg_latency_ms": 125.3
    },
    {
      "day": "2025-12-02",
      "searches": 198,
      "avg_latency_ms": 132.1
    }
  ]
}
```

### 4. GET /v1/admin/users?range=7d&page=1&page_size=50&sort=last_activity

**Query Parameters:**
- `range`: Time range for recent metrics (e.g., "7d", "30d")
- `page`: Page number (1-indexed)
- `page_size`: Items per page (max 100)
- `sort`: Sort column ("last_activity", "hours_ready", "videos_ready", "searches_7d")

**Response:**
```json
{
  "items": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "full_name": "John Doe",
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

### 5. GET /v1/admin/users/{user_id}

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
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

## Frontend Pages

### Admin Dashboard: /admin

Features:
- KPI cards (videos, success rate, hours, searches)
- Throughput chart (last 14 days of 30-day data)
- Search activity chart (last 14 days of 30-day data)
- Sortable users table with click-to-drilldown

### User Detail: /admin/users/{id}

Features:
- User summary metrics
- Recent videos table (last 20)
- Recent searches table (last 50)
- Back navigation to admin dashboard

## Manual Test Plan

### 1. Setup Admin Access

```bash
# In services/api/.env
ADMIN_USER_IDS=<your-user-id>
```

Restart API service.

### 2. Test Admin User Access

**Steps:**
1. Log in to Heimdex frontend as admin user
2. Navigate to `/admin` in browser
3. Verify page loads with metrics

**Expected:**
- ✅ Page displays KPI cards
- ✅ Charts show data (if available)
- ✅ Users table displays

### 3. Test Non-Admin Access

**Steps:**
1. Log out
2. Log in as non-admin user (or remove your ID from ADMIN_USER_IDS)
3. Navigate to `/admin`

**Expected:**
- ❌ "Access Denied" error message
- ✅ Button to return to dashboard

### 4. Test API Endpoints Directly

```bash
# Get your JWT token from browser localStorage or network tab
TOKEN="your-jwt-token"

# Test overview
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/overview

# Test throughput
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/admin/timeseries/throughput?range=30d&bucket=day"

# Test users list
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/admin/users?range=7d&page=1&page_size=50&sort=last_activity"
```

**Expected:**
- ✅ Admin user: 200 OK with JSON data
- ❌ Non-admin user: 403 Forbidden

### 5. Test User Drilldown

**Steps:**
1. From admin dashboard, click on a user row
2. Verify navigation to `/admin/users/{id}`
3. Verify user details, videos, and searches display

**Expected:**
- ✅ User summary metrics display
- ✅ Recent videos table shows correct data
- ✅ Recent searches table shows correct data
- ✅ "Back to Admin Dashboard" button works

### 6. Test Sorting and Pagination

**Steps:**
1. On admin dashboard users table
2. Change sort dropdown to different options
3. Verify table reorders

**Expected:**
- ✅ Sorting by "Last Activity" shows most recent first
- ✅ Sorting by "Hours Processed" shows highest first
- ✅ Sorting by "Videos Processed" shows highest first
- ✅ Sorting by "Recent Searches" shows most active first

## Troubleshooting

### "Not authorized" error

**Cause:** User ID not in ADMIN_USER_IDS allowlist

**Fix:**
1. Get your user ID from Supabase dashboard or browser console
2. Add to ADMIN_USER_IDS in `.env`
3. Restart API service

### "Failed to fetch admin data" error

**Cause:** RPC functions not created in database

**Fix:**
1. Run migration 018: `psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql`
2. Verify functions exist: `SELECT routine_name FROM information_schema.routines WHERE routine_name LIKE 'get_admin%';`

### Charts show "No data available"

**Cause:** No videos or searches in time range

**Expected:** This is normal for new deployments. Upload videos and perform searches to populate data.

### Users table empty

**Cause:** No user profiles created yet

**Fix:** Ensure users complete onboarding flow to create `user_profiles` records.

## Phase 1 Limitations

**Known limitations (to be addressed in Phase 2):**

1. **Processing time metrics:** Uses `videos.updated_at` as completion time proxy (not exact)
2. **No per-stage failure tracking:** Overall failure rate only
3. **No RTF (Real-Time Factor):** Requires processing duration timestamps
4. **No storage metrics:** File sizes not tracked in database
5. **Simple charts:** Text-based tables instead of visual charts (can add chart library later)
6. **No total user count:** Pagination metadata limited

## Next Steps (Phase 2)

1. Add processing timestamps (migration 019):
   - `videos.processing_started_at`
   - `videos.processing_finished_at`
   - `videos.processing_duration_ms`

2. Add visual charts library (e.g., Chart.js, Recharts)

3. Add file size tracking for storage metrics

4. Add per-stage failure tracking

5. Add export functionality (CSV/Excel)

6. Add date range picker for flexible time windows
