# Bug Fix: Photo Download Method Signature Mismatch

## Issue
When processing reference photos, the worker failed with:
```
TypeError: SupabaseStorage.download_file() missing 1 required positional argument: 'local_path'
```

## Root Cause
The `PersonPhotoProcessor` was calling `storage.download_file()` with only one argument (storage path), attempting to get bytes back and write them manually. However, the `SupabaseStorage.download_file()` method signature requires TWO arguments: both the storage path and the local file path to write to.

### Storage Adapter Signature
```python
# services/worker/src/adapters/supabase.py
def download_file(self, storage_path: str, local_path: Path) -> None:
    """
    Download file from storage to local path.

    Args:
        storage_path: Path to the file in storage
        local_path: Local file path to save to

    Returns:
        None: This function does not return a value.
    """
    logger.info(f"Downloading {storage_path} to {local_path}")
    file_bytes = self.client.storage.from_(self.bucket_name).download(storage_path)
    local_path.write_bytes(file_bytes)
    logger.info(f"Downloaded {len(file_bytes)} bytes")
```

### Incorrect Usage
```python
# services/worker/src/domain/person_photo_processor.py (BEFORE)
# Download photo to temporary directory
with TemporaryDirectory() as tmpdir:
    local_path = Path(tmpdir) / f"photo_{photo_id}.jpg"

    logger.info(f"Downloading photo from {storage_path}")
    photo_data = self.storage.download_file(storage_path)  # ❌ Missing local_path
    local_path.write_bytes(photo_data)  # ❌ Trying to manually write bytes
```

## Files Changed

### `services/worker/src/domain/person_photo_processor.py` (lines 64-70)

**Before:**
```python
# Download photo to temporary directory
with TemporaryDirectory() as tmpdir:
    local_path = Path(tmpdir) / f"photo_{photo_id}.jpg"

    logger.info(f"Downloading photo from {storage_path}")
    photo_data = self.storage.download_file(storage_path)
    local_path.write_bytes(photo_data)
```

**After:**
```python
# Download photo to temporary directory
with TemporaryDirectory() as tmpdir:
    local_path = Path(tmpdir) / f"photo_{photo_id}.jpg"

    logger.info(f"Downloading photo from {storage_path}")
    self.storage.download_file(storage_path, local_path)
```

## Solution

Simply pass both required arguments to `download_file()`:
1. `storage_path` - where to download from
2. `local_path` - where to save the file

The storage adapter handles:
- Downloading bytes from Supabase storage
- Writing bytes to local file
- Logging download progress

This is cleaner than manually handling bytes in the processor.

## Deployment

Rebuild and restart worker:
```bash
docker-compose build worker
docker-compose up -d worker
```

Verify startup:
```bash
docker-compose logs worker --tail 20
```

Should see:
```
worker-1  | 2026-01-05 10:37:40,359 - src.tasks - INFO - Worker bootstrapped successfully
worker-1  | 2026-01-05 10:37:40,374 - dramatiq.MainProcess - INFO - Dramatiq '2.0.0' is booting up.
```

## Testing

After deployment:
1. Navigate to `/people`
2. Create a person (or use existing)
3. Upload reference photo(s)
4. Monitor worker logs:
   ```bash
   docker-compose logs worker -f
   ```
5. Should see successful processing:
   ```
   Starting reference photo processing for photo_id={uuid}
   Downloading photo from persons/.../refs/{photo_id}.jpg
   Downloaded {size} bytes
   Generating CLIP embedding for {local_path}
   Photo {photo_id} marked as READY
   Completed reference photo processing for photo_id={uuid}
   ```
6. Verify photo state transitions: UPLOADED → PROCESSING → READY
7. Verify person status becomes READY

## Impact
- **Severity**: Critical (photo processing completely broken)
- **Scope**: All reference photo uploads
- **User Impact**: Photos stuck in PROCESSING state forever
- **Time to Fix**: ~2 minutes (simple argument fix)

## Root Cause Analysis

**Why did this happen?**

This appears to be a mismatch between the API contract and its usage:

1. **Storage adapter designed for file-to-file operations**
   - Takes `local_path` as argument
   - Writes bytes internally
   - Returns `None`

2. **Processor assumed bytes-returning API**
   - Tried to get bytes back from `download_file()`
   - Attempted to manually write bytes
   - This is a common pattern in other storage libraries

3. **Similar to video processor**
   - Video processor likely uses same pattern correctly
   - Person photo processor may have been written without checking existing usage

**Where did the pattern come from?**

Let me check if video processor has similar code... The storage adapter was designed to handle file I/O internally, which is cleaner and safer. The processor code should have followed this pattern from the start.

## Lessons Learned

1. **Check method signatures before calling**
   - Read the actual implementation
   - Don't assume API based on naming alone
   - Type hints help but need to be checked

2. **Follow existing patterns in codebase**
   - Video processor likely does this correctly
   - Copy working patterns from similar code
   - Don't reinvent patterns already established

3. **IDE/type checking would catch this**
   - TypeScript would catch this at compile time
   - Python type hints + mypy would catch it
   - But we're not running mypy in CI

4. **Unit tests would catch this**
   - Mock test calling storage.download_file()
   - Would fail immediately with wrong arguments
   - Integration tests even better

## Prevention

1. **Add type checking to worker CI**
   ```bash
   mypy services/worker/src --strict
   ```

2. **Add unit tests for processors**
   - Mock storage adapter
   - Verify correct method calls
   - Test argument passing

3. **Review similar code before implementing**
   - Check video_processor.py for download patterns
   - Follow established conventions
   - Ask if API seems unusual

4. **Add integration smoke tests**
   - Actually run photo processing with test photo
   - Catch errors before production
   - Could be part of CI pipeline

## Related Issues

This is the **fifth deployment bug** in People feature:
1. devlog/2601051844.txt - Response wrapper mismatches
2. devlog/2601051853.txt - Query parameter issue
3. devlog/2601051907.txt - Worker import error
4. devlog/2601051917.txt - JSON parse error on delete
5. BUGFIX_PHOTO_DOWNLOAD.md - Storage method signature (current)

All bugs found through manual testing after deployment, suggesting need for automated testing.
