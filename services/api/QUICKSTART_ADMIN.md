# Admin Metrics Quick Start Guide

## 1. Apply Database Migration

```bash
cd /Users/jangwonlee/Projects/demo-heimdex-v3
psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql
```

Or in Supabase Dashboard:
1. Go to SQL Editor
2. Copy/paste contents of `infra/migrations/018_add_admin_metrics_rpc_functions.sql`
3. Click "Run"

## 2. Configure Admin User

**Get your user ID:**
1. Log in to Heimdex frontend at http://localhost:3000
2. Open browser console (F12 → Console tab)
3. Run this command:
   ```javascript
   (await supabase.auth.getSession()).data.session?.user?.id
   ```
4. Copy the UUID (e.g., `123f1234-1234-1234-1234-faf71a7412345`)

**Add to environment file:**

Edit `services/api/.env` and add:
```bash
ADMIN_USER_IDS=123f1234-1234-1234-1234-faf71a7412345
```

**Multiple admins:**
```bash
ADMIN_USER_IDS=uuid1,uuid2,uuid3
```

## 3. Restart API Service

```bash
cd services/api

# If running with uvicorn directly:
uvicorn src.main:app --reload

# Or with Docker Compose:
docker-compose restart api
```

## 4. Verify Configuration

**Test the config is loaded:**

```bash
cd services/api
python3 -c "from src.config import settings; print('Admin IDs:', settings.admin_user_ids_list)"
```

Expected output:
```
Admin IDs: ['799f1283-a2d7-4f8a-96e6-faf71a749b64']
```

If you see `Admin IDs: []`, the environment variable is not being read. Check:
1. `.env` file exists in `services/api/` directory
2. `ADMIN_USER_IDS` is set in that file (no spaces around `=`)
3. You restarted the API service after editing `.env`

## 5. Test Admin Access

### From Frontend

1. Navigate to http://localhost:3000/admin
2. You should see the admin dashboard with metrics

**If you see "Access Denied":**
- Verify your user ID matches what's in `ADMIN_USER_IDS`
- Check API logs for authentication errors

### From API Directly

```bash
# Get your JWT token from browser
# (Open Network tab, copy Authorization header from any API request)
TOKEN="your-jwt-token-here"

# Test admin endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/overview
```

**Expected response (200 OK):**
```json
{
  "videos_ready_total": 0,
  "videos_failed_total": 0,
  "videos_total": 0,
  "failure_rate_pct": 0.0,
  "hours_ready_total": 0.0,
  ...
}
```

**If you get 403 Forbidden:**
```json
{
  "detail": "Admin privileges required"
}
```

This means either:
1. Your user ID is not in `ADMIN_USER_IDS`
2. The environment variable wasn't loaded (restart API)
3. You're logged in as a different user

## 6. Troubleshooting

### Issue: Empty admin_user_ids_list

**Check config loading:**
```bash
cd services/api
python3 << 'EOF'
from src.config import settings
print("Raw admin_user_ids:", repr(settings.admin_user_ids))
print("Parsed list:", settings.admin_user_ids_list)
EOF
```

**If raw value is empty string:**
- Check `.env` file path: `services/api/.env`
- Verify `ADMIN_USER_IDS=...` line exists
- No extra quotes: `ADMIN_USER_IDS=uuid` not `ADMIN_USER_IDS="uuid"`

### Issue: 403 Forbidden despite correct config

**Check JWT user ID matches:**
```bash
# Decode your JWT token (from browser)
# Visit https://jwt.io and paste your token
# Look for "sub" field - this is your user_id
```

Verify the "sub" (subject) field matches the UUID in `ADMIN_USER_IDS`.

### Issue: Migration already applied

If you get "already exists" errors when running the migration:

```bash
# Drop the functions first
psql $DATABASE_URL << 'EOF'
DROP FUNCTION IF EXISTS get_admin_overview_metrics();
DROP FUNCTION IF EXISTS get_throughput_timeseries(INT);
DROP FUNCTION IF EXISTS get_search_timeseries(INT);
DROP FUNCTION IF EXISTS get_admin_users_list(INT, INT, INT, TEXT);
DROP FUNCTION IF EXISTS get_admin_user_detail(TEXT, INT);
EOF

# Then re-run the migration
psql $DATABASE_URL -f infra/migrations/018_add_admin_metrics_rpc_functions.sql
```

## 7. Production Deployment

### Railway (API)

1. Go to Railway dashboard → Your project → api service
2. Go to "Variables" tab
3. Add new variable:
   - Name: `ADMIN_USER_IDS`
   - Value: `your-user-id-1,your-user-id-2`
4. Click "Save"
5. Service will automatically redeploy

### Supabase (Database)

1. Go to Supabase dashboard → SQL Editor
2. Paste migration 018 content
3. Run (one-time setup)

### Vercel (Frontend)

No changes needed - frontend automatically uses `/admin` routes.

## 8. Getting User IDs for Production

**Method 1: From Supabase Dashboard**
1. Go to Supabase Dashboard → Authentication → Users
2. Find the user
3. Copy their UUID from the table

**Method 2: From Production Frontend**
1. Log in as the user
2. Open browser console
3. Run: `(await supabase.auth.getSession()).data.session?.user?.id`

**Method 3: From SQL**
```sql
SELECT id, email FROM auth.users WHERE email = 'admin@example.com';
```

## Summary Checklist

- [ ] Migration 018 applied to database
- [ ] `ADMIN_USER_IDS` set in `services/api/.env` (local) or Railway variables (production)
- [ ] API service restarted
- [ ] Config verification command shows correct user IDs
- [ ] Admin user can access `/admin` page
- [ ] Non-admin user gets 403 error

---

**Need help?** See full documentation in `services/api/ADMIN_METRICS_SETUP.md`
