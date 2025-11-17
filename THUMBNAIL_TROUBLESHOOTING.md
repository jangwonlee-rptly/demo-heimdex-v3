# Thumbnail Troubleshooting Guide

## Quick Diagnosis

### Check if thumbnails exist in database:

```sql
-- Check video thumbnails
SELECT
    id,
    status,
    thumbnail_url IS NOT NULL as has_thumbnail,
    thumbnail_url
FROM videos
ORDER BY created_at DESC
LIMIT 5;

-- Check scene thumbnails
SELECT
    v.id as video_id,
    v.status,
    COUNT(vs.id) as total_scenes,
    COUNT(vs.thumbnail_url) as scenes_with_thumbnails
FROM videos v
LEFT JOIN video_scenes vs ON vs.video_id = v.id
GROUP BY v.id, v.status
ORDER BY v.created_at DESC;
```

---

## Common Issues & Fixes

### Issue 1: Thumbnails Not Uploading

**Symptoms:**
- `thumbnail_url` is NULL in database
- Worker logs show upload errors

**Check:**
```bash
# Look for errors in worker logs
docker logs worker-container 2>&1 | grep -i "thumbnail\|upload"
```

**Common Causes:**

1. **Storage bucket doesn't exist**
   ```sql
   -- Check in Supabase dashboard: Storage > videos bucket exists?
   ```

2. **Permission issues**
   - Service role key needs storage write access
   - Check: Supabase Dashboard > Settings > API > service_role key

3. **Local file not generated**
   ```bash
   # Worker should create these files:
   # /tmp/heimdex/{video_id}/scene_0_frame_0.jpg
   ```

**Fix:**
```bash
# Reprocess the video
curl -X POST "https://your-api.com/videos/{video_id}/process" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Issue 2: Thumbnails Uploaded But Not Displaying

**Symptoms:**
- `thumbnail_url` exists in database
- Images don't load in frontend

**Check URL accessibility:**
```bash
# Copy thumbnail_url from database and try in browser
# Should load an image

# Or use curl:
curl -I "https://oxmfngfqmedbzgknyijj.supabase.co/storage/v1/object/public/videos/{path}"
```

**Common Causes:**

1. **Bucket not public**
   - Supabase Dashboard > Storage > videos > Make bucket public

2. **CORS issues**
   - Add your frontend domain to allowed origins
   - Supabase Dashboard > Storage > videos > CORS settings

3. **Wrong URL format**
   - Should be: `https://{project}.supabase.co/storage/v1/object/public/videos/{path}`
   - NOT: `https://{project}.supabase.co/storage/v1/object/videos/{path}` (missing "public")

**Fix:**
```sql
-- If URLs are malformed, update them:
UPDATE video_scenes
SET thumbnail_url = REPLACE(
    thumbnail_url,
    '/storage/v1/object/videos/',
    '/storage/v1/object/public/videos/'
)
WHERE thumbnail_url LIKE '%/storage/v1/object/videos/%';
```

---

### Issue 3: Thumbnails for Old Videos Missing

**Symptoms:**
- New videos have thumbnails
- Old videos (uploaded before fixes) don't

**Fix:**
Reprocess old videos:

```bash
# Get list of videos without thumbnails
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-api.com/videos" | jq '.videos[] | select(.thumbnail_url == null) | .id'

# Reprocess each one
curl -X POST "https://your-api.com/videos/{video_id}/process" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Verification Steps

### 1. Check Storage Bucket

```
Supabase Dashboard > Storage > Buckets
✅ "videos" bucket exists
✅ Bucket is Public
✅ CORS allowed origins include your frontend domain
```

### 2. Check Permissions

```
Supabase Dashboard > Settings > API
✅ service_role key is set in worker environment
✅ service_role has storage.objects.create permission
```

### 3. Check Worker Logs

Look for these success messages:
```
✅ "Uploading scene_0_frame_0.jpg (12345 bytes) to ..."
✅ "Successfully uploaded to ..."
✅ "Thumbnail URL: https://..."
```

Look for these error patterns:
```
❌ "Failed to upload"
❌ "Permission denied"
❌ "Bucket not found"
❌ "Local file not found"
```

### 4. Check Database

```sql
-- Should see thumbnails for all ready videos
SELECT
    COUNT(*) FILTER (WHERE thumbnail_url IS NOT NULL) as with_thumbnails,
    COUNT(*) FILTER (WHERE thumbnail_url IS NULL) as without_thumbnails,
    COUNT(*) as total
FROM videos
WHERE status = 'READY';
```

---

## Manual Upload Test

Test thumbnail upload manually:

```python
# In worker container
from pathlib import Path
from src.adapters.supabase import storage

# Create a test image
test_file = Path("/tmp/test.jpg")
# ... create a small test image ...

# Try upload
url = storage.upload_file(
    test_file,
    "test/manual_test.jpg",
    "image/jpeg"
)
print(f"Uploaded to: {url}")

# Try to access in browser
# https://{project}.supabase.co/storage/v1/object/public/videos/test/manual_test.jpg
```

---

## Improved Worker Logs

After the fix, you should see detailed logs:

```
[INFO] Uploading scene_0_frame_0.jpg (15234 bytes) to 799.../abc.../thumbnails/scene_0.jpg
[INFO] Read 15234 bytes from /tmp/heimdex/abc.../scene_0_frame_0.jpg
[DEBUG] File check result: 404
[INFO] Uploading 15234 bytes to 799.../abc.../thumbnails/scene_0.jpg
[INFO] Successfully uploaded to 799.../abc.../thumbnails/scene_0.jpg
[INFO] Thumbnail URL: https://oxmfngfqmedbzgknyijj.supabase.co/storage/v1/object/public/videos/799.../abc.../thumbnails/scene_0.jpg
```

---

## Quick Fix Commands

```bash
# 1. Make bucket public (if not already)
# Do this in Supabase Dashboard: Storage > videos > Make public

# 2. Reprocess all failed videos
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-api.com/videos" | \
  jq -r '.videos[] | select(.status == "FAILED") | .id' | \
  while read id; do
    echo "Reprocessing $id"
    curl -X POST "https://your-api.com/videos/$id/process" \
      -H "Authorization: Bearer $TOKEN"
  done

# 3. Reprocess videos without thumbnails
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-api.com/videos" | \
  jq -r '.videos[] | select(.thumbnail_url == null and .status == "READY") | .id' | \
  while read id; do
    echo "Reprocessing $id"
    curl -X POST "https://your-api.com/videos/$id/process" \
      -H "Authorization: Bearer $TOKEN"
  done
```

---

## Expected Behavior After Fix

1. **During Processing:**
   - Worker extracts keyframes
   - Uploads to Supabase Storage
   - Saves URL to database
   - Detailed logs show each step

2. **Retry/Idempotency:**
   - Checks if file exists before upload
   - Skips upload if already present
   - Returns existing URL

3. **Error Handling:**
   - Gracefully handles 409 Duplicate errors
   - Logs detailed error messages
   - Falls back to URL generation if get_public_url fails

---

## Still Having Issues?

1. **Share worker logs** from a processing attempt
2. **Check Supabase Dashboard** > Storage > videos > Files
3. **Verify** bucket is public
4. **Test** thumbnail URL directly in browser

