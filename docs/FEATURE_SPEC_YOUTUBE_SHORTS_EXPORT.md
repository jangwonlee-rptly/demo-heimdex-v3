# Feature Specification: YouTube Shorts Export

**Status:** Planning
**Created:** 2025-12-10
**Author:** Product Planning

---

## Executive Summary

Enable users to export individual video scenes as YouTube Shorts-compliant vertical videos (9:16 aspect ratio, max 180 seconds). This feature leverages existing scene detection and metadata to create shareable, platform-optimized short-form content.

---

## 1. Current State Analysis

### Available Data per Scene
From `VideoScene` model (services/api/src/domain/models.py:144-195):
- ✅ `start_s` - Scene start timestamp
- ✅ `end_s` - Scene end timestamp
- ✅ `transcript_segment` - Scene-specific transcript
- ✅ `visual_summary` - AI-generated visual description
- ✅ `visual_description` - Rich 1-2 sentence description (v2)
- ✅ `visual_entities` - Detected entities (v2)
- ✅ `visual_actions` - Detected actions (v2)
- ✅ `tags` - Normalized tags (v2)
- ✅ `thumbnail_url` - Scene thumbnail image

### Existing Technical Capabilities
- ✅ FFmpeg adapter with frame extraction (services/worker/src/adapters/ffmpeg.py:564-595)
- ✅ Supabase storage integration for video files
- ✅ Scene-level metadata and timestamps
- ✅ Worker task queue infrastructure (Redis/TaskIQ)

### Current User Experience
- Users can view scenes in video details page (services/frontend/src/app/videos/[id]/page.tsx:660-679)
- Clicking a scene jumps video player to that timestamp
- No export functionality exists yet

---

## 2. YouTube Shorts Requirements (2025)

### Video Specifications
| Requirement | Value | Source |
|------------|-------|--------|
| **Aspect Ratio** | 9:16 (vertical) | YouTube Platform Requirement |
| **Resolution** | 1080×1920 (recommended) | YouTube Platform Requirement |
| **Duration** | ≤ 180 seconds (3 minutes) | YouTube Platform Requirement |
| **File Size** | < 60MB (recommended) | YouTube Platform Best Practice |
| **Format** | MP4 (H.264 + AAC) | YouTube Platform Requirement |

### Constraints for Our Implementation
- Source videos may not be 9:16 (likely 16:9 landscape)
- Scene duration: `end_s - start_s` must be ≤ 180s
- Need to handle aspect ratio conversion (crop/letterbox/pillarbox)

---

## 3. Feature Scope

### 3.1 Core Functionality (MVP)

**User Action:**
1. User views video details page with detected scenes
2. User clicks "Export to YouTube Short" button on a scene card
3. System extracts scene clip and converts to 9:16 format
4. User downloads the processed Short to their device

**Technical Flow:**
```
[Frontend] → [API Endpoint] → [Worker Task] → [Video Processing] → [Storage] → [Download URL]
```

### 3.2 Out of Scope (Future)
- ❌ Direct upload to YouTube API (requires OAuth integration)
- ❌ Custom captions/subtitles overlay (use transcript in description instead)
- ❌ Music/audio track replacement
- ❌ Multi-scene compilation
- ❌ Custom branding/watermarks
- ❌ Advanced editing (transitions, effects, filters)

---

## 4. User Stories

### Primary User Story
**As a** video content creator
**I want to** export a scene from my video as a YouTube Short
**So that** I can easily repurpose interesting moments as shareable short-form content

**Acceptance Criteria:**
- Scene duration must be ≤ 180 seconds
- Output video is 9:16 aspect ratio, 1080×1920 resolution
- Output includes audio from original scene
- Original video quality is preserved (no unnecessary re-encoding)
- Export completes within reasonable time (< 30 seconds for 60s scene)

### Secondary User Stories

**As a** user with landscape videos
**I want** the system to intelligently crop or letterbox the content
**So that** my 16:9 footage fits the 9:16 format without distortion

**As a** user
**I want** to know the export status (processing, ready, failed)
**So that** I can download the Short when it's ready

---

## 5. Technical Requirements

### 5.1 Backend - New API Endpoint

**Endpoint:** `POST /v1/scenes/{scene_id}/export-short`

**Request:**
```json
{
  "aspect_ratio_strategy": "center_crop" | "letterbox" | "smart_crop",
  "output_quality": "high" | "medium"  // Optional, default: high
}
```

**Response (202 Accepted):**
```json
{
  "export_id": "uuid",
  "scene_id": "uuid",
  "status": "pending",
  "created_at": "2025-12-10T12:00:00Z"
}
```

**Response (when checking status - GET /v1/exports/{export_id}):**
```json
{
  "export_id": "uuid",
  "scene_id": "uuid",
  "status": "completed" | "processing" | "failed",
  "download_url": "https://...",  // Presigned URL, valid 1 hour
  "file_size_bytes": 12345678,
  "duration_s": 45.2,
  "error_message": null,
  "created_at": "2025-12-10T12:00:00Z",
  "completed_at": "2025-12-10T12:00:30Z"
}
```

### 5.2 Database Schema

**New Table: `scene_exports`**
```sql
CREATE TABLE scene_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Export configuration
    aspect_ratio_strategy TEXT NOT NULL,  -- 'center_crop', 'letterbox', 'smart_crop'
    output_quality TEXT NOT NULL,         -- 'high', 'medium'

    -- Processing status
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,

    -- Output metadata
    storage_path TEXT,           -- Path in Supabase storage
    file_size_bytes BIGINT,
    duration_s FLOAT,
    resolution TEXT,             -- e.g., "1080x1920"

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,      -- Automatically set to created_at + 24 hours

    -- Indexes
    INDEX idx_scene_exports_scene_id (scene_id),
    INDEX idx_scene_exports_user_id (user_id),
    INDEX idx_scene_exports_status (status),
    INDEX idx_scene_exports_expires_at (expires_at)  -- For cleanup job
);
```

**Notes:**
- `expires_at` is set to `created_at + 24 hours` automatically
- Cleanup job runs periodically to delete expired exports

### 5.3 Worker - Video Processing Task

**New Task:** `export_scene_as_short(scene_id: UUID, export_id: UUID, strategy: str)`

**Processing Steps:**
1. **Fetch scene metadata** - Get start_s, end_s, video_id from database
2. **Download source video** - From Supabase storage to worker temp directory
3. **Extract scene clip** - Use FFmpeg to extract time range [start_s, end_s]
4. **Convert aspect ratio** - Apply selected strategy:
   - **center_crop**: Crop center of 16:9 to 9:16 (lose sides)
   - **letterbox**: Add black bars top/bottom (no content loss)
   - **smart_crop**: Detect focal point and crop intelligently (advanced)
5. **Encode to YouTube Shorts spec**:
   - Resolution: 1080×1920
   - Codec: H.264 (libx264)
   - Audio: AAC
   - Bitrate: 8-10 Mbps (high quality)
   - File size: < 60MB
6. **Upload to storage** - Save to `exports/{user_id}/{export_id}.mp4`
7. **Update database** - Mark export as completed with metadata

**FFmpeg Command Template (center_crop):**
```bash
ffmpeg -i input.mp4 \
  -ss {start_s} \
  -to {end_s} \
  -vf "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos" \
  -c:v libx264 -preset slow -crf 18 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  output.mp4
```

**FFmpeg Command Template (letterbox):**
```bash
ffmpeg -i input.mp4 \
  -ss {start_s} \
  -to {end_s} \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset slow -crf 18 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  output.mp4
```

### 5.4 Frontend - UI Components

**Location:** Video details page (services/frontend/src/app/videos/[id]/page.tsx)

**New UI Element:** "Export to Short" button on each scene card

**Modal Dialog:** Export configuration
- Aspect ratio strategy selector (visual preview)
- Quality preset dropdown
- Scene duration warning if > 180s
- "Export" and "Cancel" buttons

**Export Status Indicator:**
- Toast notification: "Export started..."
- Progress indicator (if worker supports progress updates)
- Download button when ready

**New Page (Optional):** `/exports` - View all user's exports with download links

---

## 6. Implementation Plan

### Phase 1: Backend Foundation (4-6 hours)
1. ✅ Create database migration for `scene_exports` table (with expires_at field)
2. ✅ Add `SceneExport` model to domain/models.py
3. ✅ Create `/v1/scenes/{scene_id}/export-short` POST endpoint
   - **Rate limiting:** Check user hasn't exceeded 10 exports in last 24 hours
   - **Validation:** Scene duration ≤ 180 seconds
4. ✅ Create `/v1/exports/{export_id}` GET endpoint
   - **Expiration check:** Return 404 if export expired
   - **Presigned URL:** Generate with 1-hour expiration
5. ✅ Add database adapter methods (create_export, get_export, update_export, count_user_exports_today)
6. ✅ Add custom exceptions: `ExportLimitExceededException`, `ExportExpiredException`

### Phase 2: Worker Implementation (6-8 hours)
1. ✅ Create `export_scene_as_short` task in worker/src/tasks.py
2. ✅ Implement aspect ratio conversion functions in ffmpeg adapter
3. ✅ Add video clip extraction with FFmpeg
4. ✅ Test with sample videos (16:9 → 9:16 conversion)
5. ✅ Handle error cases (scene too long, missing video, encoding failures)
6. ✅ Add cleanup for temp files
7. ✅ Set `expires_at = created_at + 24 hours` when creating export record

### Phase 3: Frontend UI (4-6 hours)
1. ✅ Add "Export to Short" button to scene cards
2. ✅ Create ExportShortModal component
3. ✅ Implement export status polling
4. ✅ Add download button with presigned URL
5. ✅ Add error handling and user feedback
   - **Rate limit error:** "Daily export limit reached (10/day). Try again tomorrow."
   - **Expired error:** "This export has expired. Please create a new export."
6. ✅ Add duration validation (warn if scene > 180s)
7. ✅ Show expiration countdown on completed exports ("Expires in 18 hours")

### Phase 4: Cleanup Job (2-3 hours)
1. ✅ Create periodic cleanup task `cleanup_expired_exports`
   - Runs every 6 hours via cron/scheduled job
   - Finds exports where `expires_at < NOW()`
   - Deletes files from Supabase storage
   - Deletes database records
2. ✅ Add monitoring/logging for cleanup operations
3. ✅ Test cleanup job with expired test data

### Phase 5: Testing & Refinement (2-4 hours)
1. ✅ Test with various video aspect ratios (16:9, 4:3, 1:1)
2. ✅ Test with different scene durations (5s, 60s, 120s, 180s)
3. ✅ Verify output quality and file size
4. ✅ Test concurrent exports
5. ✅ Test rate limiting (attempt 11 exports in one day)
6. ✅ Test expiration flow (wait 24 hours, verify cleanup)
7. ✅ Performance testing (export time vs scene duration)

**Total Estimate:** 18-27 hours

---

## 7. Key Design Decisions

### 7.1 Aspect Ratio Strategy

**Decision:** Offer 2 strategies initially (center_crop, letterbox), defer smart_crop

**Rationale:**
- **center_crop**: Simple, fast, works well for talking-head videos centered in frame
- **letterbox**: No content loss, acceptable for most use cases
- **smart_crop**: Requires ML/computer vision, significant complexity (defer to v2)

**Default:** `center_crop` (most common for social media)

### 7.2 Synchronous vs Asynchronous Export

**Decision:** Asynchronous (worker task queue)

**Rationale:**
- Video processing can take 10-30+ seconds depending on scene duration
- Prevents HTTP request timeout
- Allows user to continue browsing while export processes
- Matches existing video processing pattern

### 7.3 Storage Location

**Decision:** Store exports in Supabase storage under `exports/{user_id}/{export_id}.mp4`

**Rationale:**
- Consistent with existing video storage
- Presigned URLs for secure downloads
- Automatic cleanup possible (TTL policies)
- No additional infrastructure needed

**Cleanup Policy:** Delete exports after **24 hours** (decided)
- Minimizes storage costs
- Encourages prompt downloads
- Users can re-export within daily limit if needed

### 7.4 Quality Presets

**Decision:** Offer 2 quality levels (high, medium)

**High Quality:**
- Resolution: 1080×1920
- Bitrate: 8-10 Mbps
- CRF: 18
- Target: < 60MB

**Medium Quality:**
- Resolution: 1080×1920
- Bitrate: 4-6 Mbps
- CRF: 23
- Target: < 30MB

**Default:** High quality (YouTube recommends high quality for Shorts)

---

## 8. Error Handling

### Validation Errors (400)
- Scene duration > 180 seconds → "Scene too long for YouTube Short (max 180s)"
- Scene not found → "Scene not found"
- Video not in READY status → "Video not ready for export"
- Invalid aspect ratio strategy → "Invalid aspect ratio strategy. Choose 'center_crop' or 'letterbox'"

### Processing Errors (500)
- FFmpeg encoding failure → "Video encoding failed"
- Storage upload failure → "Failed to save export"
- Source video download failure → "Failed to access source video"

### Business Logic Errors (409)
- Export already in progress for this scene → "Export already in progress"

### Rate Limit Errors (429)
- Daily export limit exceeded → "Daily export limit reached (10/day). Try again in X hours."

### Not Found Errors (404)
- Export expired → "This export has expired (24-hour limit). Please create a new export."
- Export not found → "Export not found"

### User Feedback
- All errors logged with export_id for debugging
- User-friendly error messages displayed in UI
- Option to retry failed exports

---

## 9. Success Metrics

### Performance Metrics
- **Export Time:** < 30 seconds for 60-second scene (target)
- **Success Rate:** > 95% of exports complete successfully
- **File Size:** 80% of exports < 60MB

### Usage Metrics
- Number of exports per user per week
- Most popular aspect ratio strategy
- Average scene duration exported
- Export-to-download conversion rate

### Quality Metrics
- User satisfaction (future survey)
- Number of failed exports / retry attempts
- Output video quality complaints

---

## 10. Future Enhancements (V2+)

### High Priority
1. **Smart Crop** - ML-based focal point detection for intelligent cropping
2. **Batch Export** - Export multiple scenes at once
3. **Direct YouTube Upload** - OAuth integration for one-click publish
4. **Custom Captions** - Burn-in transcript as subtitles

### Medium Priority
5. **Scene Trimming** - Allow user to adjust start/end times before export
6. **Quality Preview** - Show preview of cropped area before export
7. **Export Templates** - Save preferred settings (strategy, quality)
8. **Export History** - Dedicated page showing all past exports

### Low Priority
9. **Audio Replacement** - Add background music from library
10. **Branding** - Add watermark/logo overlay
11. **Multi-platform Export** - TikTok, Instagram Reels presets
12. **AI-powered Highlights** - Auto-suggest best scenes to export

---

## 11. Open Questions - ✅ DECISIONS MADE

### Decisions
1. **Export limit per user:** ✅ **10 exports per day for free users**
   - Prevents abuse and manages infrastructure costs
   - Sufficient for typical use cases
   - Foundation for future paid tiers with higher limits

2. **File retention period:** ✅ **24 hours**
   - Short retention minimizes storage costs
   - Encourages users to download promptly
   - Reduces cleanup complexity
   - Users can re-export if needed (within daily limit)

3. **Scene trimming in MVP:** ✅ **Not included**
   - Adds significant UI complexity
   - Can be added in V2 if user feedback demands it
   - Users can use full scene duration for MVP

4. **Multiple exports of same scene:** ✅ **Keep all exports**
   - Each export may use different settings (crop strategy, quality)
   - Simpler logic - no deduplication needed
   - Storage cost minimal with 24-hour retention

5. **YouTube metadata generation:** ✅ **Out of scope for MVP**
   - Users can manually copy scene metadata (visual_summary, tags) when uploading
   - Can be added in V2 as "Copy to clipboard" feature
   - Avoids complexity of metadata formatting

### Technical Considerations
1. **Storage costs** - How much storage will exports consume?
2. **Worker capacity** - Can worker handle concurrent export jobs?
3. **Bandwidth** - Download from storage + upload to storage = 2x video size
4. **FFmpeg performance** - Test encoding speed on actual worker hardware

---

## 12. Rate Limiting & Cleanup Implementation

### 12.1 Rate Limiting Logic

**Endpoint:** `POST /v1/scenes/{scene_id}/export-short`

**Implementation:**
```python
async def create_scene_export(scene_id: UUID, user_id: UUID, ...):
    # Count user's exports in last 24 hours
    export_count = await db.count_user_exports_since(
        user_id=user_id,
        since=datetime.utcnow() - timedelta(hours=24)
    )

    if export_count >= 10:
        # Calculate time until oldest export expires (becomes available again)
        oldest_export = await db.get_oldest_user_export_today(user_id)
        hours_until_reset = calculate_hours_until_reset(oldest_export.created_at)

        raise ExportLimitExceededException(
            message=f"Daily export limit reached (10/day). Try again in {hours_until_reset} hours.",
            details={"current_count": export_count, "limit": 10}
        )

    # Create export...
```

**Database Query:**
```sql
SELECT COUNT(*) FROM scene_exports
WHERE user_id = $1
  AND created_at > NOW() - INTERVAL '24 hours';
```

### 12.2 Cleanup Job

**Task:** `cleanup_expired_exports` (scheduled every 6 hours)

**Implementation:**
```python
async def cleanup_expired_exports():
    """
    Delete expired exports (older than 24 hours).
    Runs every 6 hours via scheduled task.
    """
    logger.info("Starting cleanup of expired exports")

    # Find expired exports
    expired_exports = await db.get_expired_exports()

    deleted_count = 0
    failed_count = 0

    for export in expired_exports:
        try:
            # Delete from storage
            if export.storage_path:
                await storage.delete_file(export.storage_path)

            # Delete from database
            await db.delete_export(export.id)

            deleted_count += 1
            logger.info(f"Deleted expired export {export.id}")

        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to delete export {export.id}: {e}")

    logger.info(
        f"Cleanup completed: {deleted_count} deleted, {failed_count} failed"
    )

    return {"deleted": deleted_count, "failed": failed_count}
```

**Database Query:**
```sql
SELECT * FROM scene_exports
WHERE expires_at < NOW()
  AND status = 'completed';  -- Only cleanup completed exports
```

**Scheduling Options:**
1. **Cron job** in worker container (recommended)
2. **TaskIQ scheduled task** (if using TaskIQ scheduler)
3. **Separate cleanup service** (overkill for MVP)

**Recommended:** Cron job in worker container
```bash
# Add to worker Dockerfile or docker-compose
0 */6 * * * python -m src.tasks.cleanup_expired_exports
```

### 12.3 Expiration Display

**Frontend calculation:**
```typescript
function getExpirationInfo(createdAt: string) {
  const created = new Date(createdAt);
  const expires = new Date(created.getTime() + 24 * 60 * 60 * 1000); // +24 hours
  const now = new Date();

  const hoursRemaining = Math.floor((expires.getTime() - now.getTime()) / (1000 * 60 * 60));

  if (hoursRemaining < 0) {
    return { expired: true, message: "Expired" };
  }

  if (hoursRemaining < 1) {
    const minutesRemaining = Math.floor((expires.getTime() - now.getTime()) / (1000 * 60));
    return { expired: false, message: `Expires in ${minutesRemaining} minutes` };
  }

  return { expired: false, message: `Expires in ${hoursRemaining} hours` };
}
```

---

## 13. Dependencies

### External Libraries
- ✅ FFmpeg (already installed in worker container)
- ✅ Supabase Storage SDK (already in use)

### Internal Services
- ✅ Database (PostgreSQL via Supabase)
- ✅ Task Queue (Redis + TaskIQ)
- ✅ Storage (Supabase Storage)
- ✅ API (FastAPI)
- ✅ Worker (Python)

### New Dependencies
- None - all required tools already available

---

## 13. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| FFmpeg encoding failures | High | Medium | Robust error handling, retry logic, log all errors |
| Storage costs excessive | Medium | Low | Implement TTL cleanup, monitor usage |
| Worker queue backlog | High | Medium | Monitor queue depth, scale workers if needed |
| Poor output quality | High | Low | Test with various source videos, offer quality presets |
| Scene > 180s | Low | High | Frontend validation, clear error message |
| User expects direct YouTube upload | Medium | High | Clear UX copy: "Download for YouTube", not "Upload to YouTube" |

---

## 14. Testing Strategy

### Unit Tests
- Aspect ratio conversion logic
- FFmpeg command generation
- Export model validation
- API endpoint input validation

### Integration Tests
- Full export workflow (API → Worker → Storage)
- Presigned URL generation
- Export status updates
- Error handling for missing videos

### Manual Testing Checklist
- [ ] Export 16:9 landscape video scene with center_crop
- [ ] Export 16:9 landscape video scene with letterbox
- [ ] Export scene exactly 180 seconds
- [ ] Attempt export of scene > 180 seconds (should fail)
- [ ] Export scene from 4:3 aspect ratio video
- [ ] Export scene from 1:1 square video
- [ ] Verify output file plays in YouTube upload interface
- [ ] Test concurrent exports from different users
- [ ] Test multiple exports of same scene
- [ ] Verify presigned URL expiration

---

## 15. Documentation Requirements

### Developer Documentation
- API endpoint documentation (OpenAPI/Swagger)
- FFmpeg adapter new methods
- Database schema migration
- Worker task documentation

### User Documentation
- Feature announcement blog post
- Help article: "How to export a scene as YouTube Short"
- FAQ: Aspect ratio strategies explained with visuals
- Best practices: Which scenes make good Shorts?

---

## Appendix A: FFmpeg Filter Explanations

### Center Crop
```bash
crop=ih*9/16:ih
```
- Crops input to 9:16 aspect ratio
- Width = input_height * 9/16
- Height = input_height (full height)
- Crop from center (default)

### Letterbox
```bash
scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2
```
- Scale to fit within 1080×1920 (maintains aspect ratio)
- Pad with black bars to reach exact 1080×1920
- Center the video in the frame

### Scale to Output Resolution
```bash
scale=1080:1920:flags=lanczos
```
- Resize to exact 1080×1920
- Use Lanczos scaling algorithm (high quality)

---

## Appendix B: Example User Flow

1. **User uploads landscape video** (16:9, 1920×1080)
2. **System detects 15 scenes** via PySceneDetect
3. **User navigates to video details** page
4. **User finds interesting 45-second scene** (e.g., product demo)
5. **User clicks "Export to Short"** button on scene card
6. **Modal appears:**
   - Shows scene duration: 45 seconds ✓
   - Aspect ratio preview: center_crop vs letterbox
   - User selects "center_crop"
   - User clicks "Export"
7. **Toast notification:** "Export started! You'll be notified when ready."
8. **Worker processes export** (~20 seconds)
9. **Toast notification:** "Export ready! Click to download."
10. **User clicks download** → Downloads `scene_12_short.mp4`
11. **User uploads to YouTube** Shorts via web/mobile
12. **User adds title/description** using scene's visual_summary + tags

---

**End of Specification**
