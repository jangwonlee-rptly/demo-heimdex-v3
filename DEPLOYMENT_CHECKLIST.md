# Deployment Checklist for Language Preferences & Idempotency Updates

## Database Migrations Required

Run these migrations in order:

### 1. Add preferred_language to user_profiles
```bash
psql $DATABASE_URL < infra/migrations/005_add_preferred_language.sql
```

**Verify:**
```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'user_profiles' AND column_name = 'preferred_language';
```

Expected: Column exists with type `text` and default `'ko'`

---

### 2. Add full_transcript to videos
```bash
psql $DATABASE_URL < infra/migrations/006_add_transcript_cache.sql
```

**Verify:**
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'videos' AND column_name = 'full_transcript';
```

Expected: Column exists with type `text`

---

## Quick Verification Script

Run this to check all migrations:

```sql
-- Check user_profiles.preferred_language
SELECT
    CASE
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_profiles'
            AND column_name = 'preferred_language'
        )
        THEN '✅ user_profiles.preferred_language exists'
        ELSE '❌ user_profiles.preferred_language MISSING'
    END AS check_1;

-- Check videos.full_transcript
SELECT
    CASE
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'videos'
            AND column_name = 'full_transcript'
        )
        THEN '✅ videos.full_transcript exists'
        ELSE '❌ videos.full_transcript MISSING'
    END AS check_2;

-- Check that existing users have default language
SELECT
    COUNT(*) as users_without_language
FROM user_profiles
WHERE preferred_language IS NULL;
-- Expected: 0

-- Fix if needed:
-- UPDATE user_profiles SET preferred_language = 'ko' WHERE preferred_language IS NULL;
```

---

## Service Deployment Order

1. **Database** - Run migrations first
2. **API Service** - Deploy updated API with new fields
3. **Worker Service** - Deploy updated worker with idempotency
4. **Frontend** - Deploy updated frontend with language selector

---

## Testing After Deployment

### Test 1: User Profile with Language
```bash
# Get your profile
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api.com/me/profile

# Should include:
# "preferred_language": "ko"
```

### Test 2: Video Upload
```bash
# Upload a video
curl -X POST "https://your-api.com/videos/upload-url" \
  -H "Authorization: Bearer $TOKEN" \
  -d "filename=test.mp4&file_extension=mp4"

# Should return 201 with video_id
```

### Test 3: Video Processing
```bash
# Check worker logs after uploading
# Should see:
# "Processing video in language: ko"
# "Using cached transcript" (on retry)
# "Scene X already exists, skipping" (on retry)
```

---

## Rollback Plan

If issues occur:

1. **API/Worker**: Revert to previous container version
2. **Database**: Migrations are additive (safe), but to rollback:

```sql
-- Rollback full_transcript (if needed)
ALTER TABLE videos DROP COLUMN IF EXISTS full_transcript;

-- Rollback preferred_language (if needed)
ALTER TABLE user_profiles DROP COLUMN IF EXISTS preferred_language;
```

---

## Common Issues

### Issue: "unexpected keyword argument 'full_transcript'"
**Cause**: Migration not run, but new code deployed
**Fix**: Run migration 006

### Issue: "unexpected keyword argument 'preferred_language'"
**Cause**: Migration not run, but new code deployed
**Fix**: Run migration 005

### Issue: "column 'preferred_language' does not exist"
**Cause**: Migration 005 not run
**Fix**: Run migration 005

### Issue: Videos fail to upload
**Check**:
1. Are migrations run?
2. Is API container rebuilt?
3. Check API logs for actual error message

---

## Success Indicators

✅ New users see language selector in onboarding
✅ Videos process in user's preferred language
✅ Retry skips already-processed scenes
✅ Retry uses cached transcript
✅ No more 409 errors on thumbnail upload
✅ Korean filenames work properly

