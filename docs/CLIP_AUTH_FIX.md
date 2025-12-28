# CLIP Authentication Fix

**Date:** 2025-12-28
**Issue:** CLIP client HMAC authentication format mismatch
**Status:** ✅ FIXED

---

## Problem

When attempting to search, the API service failed with error:

```
2025-12-28 06:44:19,244 - src.routes.search - WARNING - CLIP text embedding failed:
CLIP service error (status=422): {"detail":[{"type":"model_attributes_type",
"loc":["body","auth"],"msg":"Input should be a valid dictionary or object to
extract fields from","input":"623be13e76aa5fa82493053461bb6ea05a19a48163dc108b14..."}]}
```

**Root Cause:**
The CLIP client was sending `auth` as a plain signature string, but the RunPod service expected an `AuthPayload` object with `ts` (timestamp) and `sig` (signature) fields.

---

## Solution

Updated `services/api/src/adapters/clip_client.py` to match RunPod service's expected format:

### Before (Incorrect)
```python
# Wrong: Sending signature as plain string
signature = self._create_hmac_signature("POST", endpoint, text=text)
payload = {
    "text": text,
    "normalize": normalize,
    "request_id": request_id,
    "auth": signature,  # ❌ Plain string
}
```

### After (Correct)
```python
# Correct: Sending auth as object with timestamp and signature
timestamp = int(time.time())
signature = self._create_hmac_signature("POST", endpoint, timestamp, text=text)
payload = {
    "text": text,
    "normalize": normalize,
    "request_id": request_id,
    "auth": {
        "ts": timestamp,      # ✅ Timestamp
        "sig": signature,     # ✅ Signature
    },
}
```

### HMAC Signature Format

Updated `_create_hmac_signature()` to match RunPod service's expected format:

```python
def _create_hmac_signature(self, method: str, path: str, timestamp: int, text: Optional[str] = None) -> str:
    """Create HMAC-SHA256 signature matching RunPod service format.

    Format:
    1. Canonical message: {method}|{path}|{text_hash}
    2. Final message: {canonical_message}|{timestamp}
    """
    # Hash the text content (don't include raw text in signature)
    if text:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        canonical_message = f"{method}|{path}|{text_hash}"
    else:
        canonical_message = f"{method}|{path}|"

    # Append timestamp to canonical message
    message_to_sign = f"{canonical_message}|{timestamp}"

    # Generate HMAC signature
    signature = hmac.new(
        self.secret_key.encode(),
        message_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()

    return signature
```

**Key changes:**
1. Added `timestamp` parameter to signature function
2. Hash the text content (not raw text in signature)
3. Canonical format: `POST|/v1/embed/text|{text_hash}|{timestamp}`
4. Return only the signature hex string

---

## Files Changed

1. **`services/api/src/adapters/clip_client.py`**
   - Updated `_create_hmac_signature()` method signature
   - Added timestamp generation
   - Fixed auth payload format

2. **`services/api/tests/integration/test_clip_search.py`**
   - Added better error handling for individual query failures
   - Continue testing even if one query fails

3. **`services/api/test_clip_auth.py`** (NEW)
   - Quick test script to verify CLIP authentication
   - Run: `python test_clip_auth.py`

---

## Testing

### Quick Test
```bash
cd services/api
python test_clip_auth.py
```

**Expected output:**
```
============================================================
CLIP Client Authentication Test
============================================================
✅ CLIP client is configured
Client: https://api-xxxx.runpod.net
Timeout: 1.5s
Max retries: 1

Testing with text: 'red car'

✅ SUCCESS!
Embedding dimension: 512
L2 norm: 1.0000
First 5 values: [0.123, -0.456, 0.789, ...]

🎉 All checks passed!
```

### Integration Test
```bash
python tests/integration/test_clip_search.py
```

### Manual Search Test
```bash
# Test via API
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "red car", "limit": 10}'
```

**Check logs for:**
```
[INFO] CLIP text embedding generated: dim=512, elapsed_ms=115
[INFO] Visual intent router: mode=recall, confidence=0.90
```

---

## Verification Checklist

- [x] CLIP client sends auth as `{ts, sig}` object
- [x] Signature includes timestamp in canonical message
- [x] Text content is hashed (not raw text in signature)
- [x] Test script created for quick verification
- [x] Integration tests updated with better error handling
- [x] Documentation updated

---

## Related Files

- **Implementation:** `services/api/src/adapters/clip_client.py`
- **Service Schema:** `services/clip-runpod-worker/app/schemas.py` (AuthPayload)
- **Service Security:** `services/clip-runpod-worker/app/security.py` (validate_auth)
- **Test Script:** `services/api/test_clip_auth.py`

---

## Future Improvements

1. **Cache validation logic:** If timestamp validation fails frequently, consider adjusting `AUTH_TIME_WINDOW_SECONDS` in RunPod service
2. **Debug mode:** Add verbose logging option to see canonical message and signature details
3. **Test coverage:** Add unit tests for HMAC signature generation

---

**Status:** ✅ Fixed and tested
**Deployed:** Pending
