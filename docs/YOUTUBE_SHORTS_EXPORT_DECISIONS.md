# YouTube Shorts Export - Decision Summary

**Date:** 2025-12-10
**Status:** Planning Complete ✅

---

## Quick Reference

### MVP Scope
- ✅ Export single scene as YouTube Short (9:16, MP4)
- ✅ Two aspect ratio strategies: center_crop, letterbox
- ✅ Two quality presets: high, medium
- ✅ Async processing via worker queue
- ✅ Download via presigned URL
- ❌ No direct YouTube upload
- ❌ No caption overlay
- ❌ No scene trimming

---

## Policy Decisions

| Policy | Decision | Rationale |
|--------|----------|-----------|
| **Export Limit** | 10 exports/day per user | Prevent abuse, manage costs |
| **File Retention** | 24 hours | Minimize storage, encourage prompt download |
| **Scene Trimming** | Not in MVP | Reduces complexity, can add later |
| **Duplicate Exports** | Keep all | Different settings, simple logic |
| **Metadata Generation** | Out of scope | Manual copy for MVP |

---

## Technical Specifications

### YouTube Shorts Requirements
- **Aspect Ratio:** 9:16 (vertical)
- **Resolution:** 1080×1920
- **Duration:** ≤ 180 seconds
- **Format:** MP4 (H.264 + AAC)
- **File Size:** < 60MB (recommended)

### Database Changes
**New Table:** `scene_exports`
- Tracks export requests and status
- Includes `expires_at` field (created_at + 24 hours)
- Indexed for cleanup queries

### API Endpoints
1. `POST /v1/scenes/{scene_id}/export-short` - Create export
2. `GET /v1/exports/{export_id}` - Get export status/download URL

### Storage
- **Location:** `exports/{user_id}/{export_id}.mp4`
- **Cleanup:** Every 6 hours via cron job
- **Download:** Presigned URL (1-hour expiration)

---

## Implementation Phases

### Phase 1: Backend (4-6 hours)
- Database migration
- API endpoints
- Rate limiting (10/day)
- Custom exceptions

### Phase 2: Worker (6-8 hours)
- FFmpeg video processing
- Aspect ratio conversion
- Scene extraction
- Error handling

### Phase 3: Frontend (4-6 hours)
- Export button on scene cards
- Export modal with settings
- Status polling
- Download with expiration timer

### Phase 4: Cleanup Job (2-3 hours)
- Scheduled cleanup task
- Delete expired files/records
- Monitoring/logging

### Phase 5: Testing (2-4 hours)
- Various aspect ratios
- Rate limiting
- Expiration flow
- Performance testing

**Total Estimate:** 18-27 hours

---

## Rate Limiting

### Logic
```python
# Count exports in last 24 hours
if user_exports_today >= 10:
    raise ExportLimitExceededException("Try again in X hours")
```

### Database Query
```sql
SELECT COUNT(*) FROM scene_exports
WHERE user_id = $1 AND created_at > NOW() - INTERVAL '24 hours';
```

---

## Cleanup Job

### Schedule
Every 6 hours via cron job in worker container

### Logic
```python
1. Find exports where expires_at < NOW()
2. Delete file from storage
3. Delete database record
4. Log results
```

### Cron Entry
```bash
0 */6 * * * python -m src.tasks.cleanup_expired_exports
```

---

## Error Handling

| Error Type | HTTP Code | Message |
|------------|-----------|---------|
| Scene too long | 400 | "Scene too long for YouTube Short (max 180s)" |
| Rate limit hit | 429 | "Daily export limit reached (10/day). Try again in X hours." |
| Export expired | 404 | "This export has expired (24-hour limit). Please create a new export." |
| Encoding failed | 500 | "Video encoding failed" |

---

## User Experience Flow

1. User clicks "Export to Short" on scene card
2. Modal shows aspect ratio options (center_crop vs letterbox)
3. User selects settings and clicks "Export"
4. Toast: "Export started! You'll be notified when ready."
5. Worker processes export (~20-30 seconds)
6. Toast: "Export ready! Click to download."
7. Download button shows "Expires in 23 hours"
8. User downloads MP4 file
9. User uploads to YouTube manually

---

## Success Metrics

### Performance Targets
- Export time: < 30 seconds for 60-second scene
- Success rate: > 95%
- File size: 80% under 60MB

### Usage Tracking
- Exports per user per day
- Popular aspect ratio strategy
- Average scene duration exported
- Failed export rate

---

## Future Enhancements (V2+)

**High Priority:**
- Smart crop (ML-based focal point detection)
- Batch export (multiple scenes)
- Direct YouTube upload (OAuth)
- Caption overlay (burn-in transcript)

**Medium Priority:**
- Scene trimming (adjust start/end)
- Quality preview before export
- Export templates (save settings)
- Export history page

**Low Priority:**
- Audio replacement
- Watermark/branding
- Multi-platform presets (TikTok, Reels)
- AI-powered scene recommendations

---

## Next Steps

**Before Implementation:**
1. ✅ Review this decision document
2. ✅ Confirm all decisions with stakeholders
3. ⬜ Begin Phase 1: Backend foundation

**Ready to Start:** Phase 1 (Backend Foundation)

---

**Full Specification:** See `FEATURE_SPEC_YOUTUBE_SHORTS_EXPORT.md`
