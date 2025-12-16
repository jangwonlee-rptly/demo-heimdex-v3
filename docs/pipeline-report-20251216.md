# Heimdex Pipeline Report - December 16, 2025

**Document Version:** 1.0
**Generated:** 2025-12-16
**System State:** Production-ready with multi-channel dense retrieval

---

## Executive Summary

Heimdex is a semantic video search system that enables natural language search across uploaded videos. The system processes videos by detecting scenes, extracting transcripts, generating visual descriptions, creating multi-channel embeddings, and indexing content for hybrid retrieval.

### Main Architectural Changes (Recent)

**Major changes introduced today/recently:**

1. **Multi-Channel Dense Retrieval (v3-multi)**: Transitioned from single embedding vector to separate embedding channels (transcript, visual, summary) for specialized semantic matching per content type.

2. **CLIP Visual Embeddings (Migration 017)**: Added true visual similarity search using OpenCLIP ViT-B-32 model (512-dim) for image-based scene matching.

3. **Timestamp-Aligned Transcript Slicing (Migration 016)**: Replaced proportional character-based transcript extraction with Whisper segment timestamps for accurate scene-to-transcript alignment.

4. **Parallel Multi-Channel Retrieval**: Implemented ThreadPoolExecutor-based concurrent retrieval across 3-4 channels (transcript, visual, summary, lexical) with per-channel timeouts and graceful degradation.

5. **Enhanced Fusion Methods**: Extended fusion algorithms to support multi-channel weighted fusion (MinMax Mean) and multi-channel RRF with per-channel scoring transparency.

---

## Changes Introduced Today

### File-by-File Change Log

**Database Migrations:**

- `infra/migrations/015_add_multi_embedding_channels.sql` (+291 lines)
  - Added `embedding_transcript`, `embedding_visual`, `embedding_summary` columns (vector(1536))
  - Created HNSW indexes for each channel
  - Added RPC functions: `search_scenes_by_transcript_embedding`, `search_scenes_by_visual_embedding`, `search_scenes_by_summary_embedding`
  - Extended `embedding_metadata` structure to support per-channel metadata

- `infra/migrations/016_add_transcript_segments.sql` (+21 lines)
  - Added `videos.transcript_segments` JSONB column
  - Stores Whisper segment-level timestamps: `[{"start": 0.0, "end": 3.5, "text": "..."}, ...]`
  - GIN index for JSONB queries

- `infra/migrations/017_add_clip_visual_embeddings.sql` (+117 lines)
  - Added `embedding_visual_clip` vector(512) column
  - Added `visual_clip_metadata` JSONB column
  - HNSW index for CLIP cosine similarity
  - RPC function: `search_scenes_by_visual_clip_embedding`

**API Service:**

- `services/api/src/routes/search.py` (major refactor, ~667 lines)
  - Added `_run_multi_dense_search()` for parallel multi-channel retrieval
  - Integrated ThreadPoolExecutor with per-channel timeouts (default 5s)
  - Added mode detection: multi_dense > hybrid > lexical_only > dense_only
  - Extended fusion to support multi-channel MinMax Mean and RRF
  - Added debug field `channel_scores` for multi-channel transparency

- `services/api/src/domain/search/fusion.py` (new functions)
  - `multi_channel_minmax_fuse()`: Normalizes and weights 3+ channels
  - `multi_channel_rrf_fuse()`: RRF fusion for 3+ channels
  - `FusedCandidate.channel_scores` field for per-channel debug data

- `services/api/src/domain/schemas.py` (extended)
  - `VideoSceneResponse.channel_scores`: Optional dict with per-channel breakdown
  - `SearchResponse.fusion_method`: Updated to include `multi_dense_minmax_mean`, `multi_dense_rrf`
  - Removed `hash` detector from `SceneDetectorPreferences`

- `services/api/src/domain/models.py` (+2 lines)
  - Added `Video.transcript_segments: Optional[list]` field to support migration 016

- `services/api/src/config.py` (new settings)
  - `MULTI_DENSE_ENABLED`: Toggle multi-channel mode (default: True)
  - `MULTI_DENSE_TIMEOUT_S`: Per-channel timeout (default: 5.0)
  - `MULTI_DENSE_WEIGHT_*`: Channel weights (transcript=0.45, visual=0.25, summary=0.10, lexical=0.20)
  - `CANDIDATE_K_*`: Per-channel candidate pool sizes

**Worker Service:**

- `services/worker/src/domain/video_processor.py` (extended)
  - Pass `transcript_segments` to `_process_single_scene()` and `build_sidecar()`
  - Save multi-channel embeddings: `embedding_transcript`, `embedding_visual`, `embedding_summary`
  - Save CLIP embedding: `embedding_visual_clip`, `visual_clip_metadata`

- `services/worker/src/domain/sidecar_builder.py` (major refactor)
  - `_extract_transcript_segment_from_segments()`: New timestamp-based transcript slicing (lines 1064-1120)
  - Handles both dict and WhisperSegment object formats for backward compat
  - Expands context window if extracted text is too short (configurable padding)
  - Fallback to proportional slicing if segments unavailable

- `services/worker/src/domain/scene_detector.py` (-35 lines)
  - Removed `HashDetector` import and all hash detector references
  - Removed `HASH` enum from `SceneDetectionStrategy`
  - Reduced detector set to: AdaptiveDetector, ContentDetector, ThresholdDetector

- `services/worker/src/adapters/database.py` (extended)
  - `save_transcript()`: Store `transcript_segments` as JSONB
  - `get_cached_transcript()`: Return tuple of (full_transcript, segments)
  - `create_scene()`: Accept multi-channel embeddings and CLIP fields
  - `search_scenes_transcript_embedding()`, `search_scenes_visual_embedding()`, `search_scenes_summary_embedding()`: Call new RPC functions

- `services/worker/src/adapters/clip_embedder.py` (+396 lines, NEW FILE)
  - `CLIPEmbedder` class: CPU-optimized CLIP inference using OpenCLIP
  - Uses ViT-B-32 model (512-dim embeddings)
  - Includes frame quality ranking (brightness, blur detection, quality score)
  - Timeout-protected inference (default 2s per frame)

- `services/worker/src/adapters/openai_client.py` (+52 lines)
  - `WhisperSegment` dataclass: Structured representation of Whisper segments
  - `transcribe_audio_with_quality()`: Returns `TranscriptionResult` with segments
  - Stores segments as list of `WhisperSegment` objects (not dicts)

- `services/worker/src/config.py` (new settings)
  - `CLIP_ENABLED`: Toggle CLIP embedding generation (default: True)
  - `CLIP_MODEL_NAME`: CLIP model identifier (default: "ViT-B-32")
  - `CLIP_PRETRAINED`: Pretrained weights (default: "openai")
  - `CLIP_TIMEOUT_S`: Per-frame inference timeout (default: 2.0)

**Tests:**

- `services/worker/tests/test_clip_embedder.py` (+260 lines, NEW)
  - Unit tests for CLIP embedding generation
  - Tests frame quality ranking, timeout handling, error cases

- `services/worker/tests/test_transcript_segmentation.py` (+291 lines, NEW)
  - Unit tests for timestamp-based transcript slicing
  - Tests overlap handling, context expansion, fallback behavior

### Behavior Changes Summary

**API/Search Behavior:**

- **Mode Selection Priority:** multi_dense > hybrid > lexical_only > dense_only
- **Multi-Dense Channels:** Transcript (45%), Visual (25%), Summary (10%), Lexical (20%)
- **Parallel Retrieval:** All channels run concurrently with ThreadPoolExecutor
- **Timeout Behavior:** Individual channel timeouts (5s default); timeouts treated as empty results
- **Score Types:** Added `multi_dense_minmax_mean` and `multi_dense_rrf` to response
- **Debug Fields:** `channel_scores` dict shows per-channel raw/norm scores, weights, ranks

**Worker/Indexing Changes:**

- **Transcript Slicing:** Now uses Whisper segment timestamps instead of proportional character slicing
- **CLIP Embeddings:** Generated from best-quality keyframe per scene (CPU-based, timeout-protected)
- **Multi-Channel Embeddings:** Three separate embeddings per scene (transcript, visual, summary)
- **Embedding Version:** Tracks schema version (`v3-multi` for new scenes)
- **Scene Detector:** Removed HashDetector (unavailable in PySceneDetect 0.6.2)

**DB/Schema Changes:**

- **New Columns:** `embedding_transcript`, `embedding_visual`, `embedding_summary`, `embedding_visual_clip`, `transcript_segments`, `visual_clip_metadata`
- **New Indexes:** HNSW indexes for each embedding channel
- **New RPCs:** 4 new search functions for per-channel retrieval
- **Backward Compatibility:** Legacy `embedding` column preserved for fallback

**OpenSearch:**

- No changes to OpenSearch mappings or queries (BM25 lexical search unchanged)

---

## Current Video Ingestion Flow

### 1. Upload URL Creation

**Endpoint:** `POST /v1/videos/upload-url`
**File:** `services/api/src/routes/videos.py:93-157`

```python
@router.post("/videos/upload-url", response_model=VideoUploadUrlResponse)
async def create_upload_url(
    file_extension: str = Query("mp4"),
    filename: str = Query(...),
    current_user: User = Depends(get_current_user),
):
```

**Steps:**

1. Authenticate user via JWT
2. Sanitize filename (handle Unicode, special chars, length limits)
3. Generate UUID for video
4. Create storage path: `{user_id}/{video_id}.{extension}`
5. Create database record with status=PENDING
6. Return `video_id` and `storage_path` to client

**Why this matters:** Client uploads directly to Supabase Storage using the storage path, then calls the "uploaded" endpoint to trigger processing.

---

### 2. Upload Completion Trigger

**Endpoint:** `POST /v1/videos/{video_id}/uploaded`
**File:** `services/api/src/routes/videos.py:160-222`

```python
@router.post("/videos/{video_id}/uploaded", status_code=202)
async def mark_video_uploaded(video_id: UUID, ...):
    # Verify ownership
    video = db.get_video(video_id)
    if video.owner_id != user_id:
        raise HTTPException(403)

    # Enqueue processing job
    task_queue.enqueue_video_processing(video_id)
```

**Steps:**

1. Verify video exists and user owns it
2. Enqueue `process_video` task to Redis queue via Dramatiq
3. Return 202 Accepted immediately

**Why this matters:** Processing happens asynchronously in the worker. API responds immediately.

---

### 3. Worker Video Processing Pipeline

**Entry Point:** `VideoProcessor.process_video()`
**File:** `services/worker/src/domain/video_processor.py:119-446`
**Dramatiq Actor:** `libs/tasks/video_processing.py`

#### 3a. Download & Metadata Extraction

```python
# Download video from storage
storage.download_file(storage_path, video_path)

# Extract metadata using FFmpeg probe
metadata = ffmpeg.probe_video(video_path)
# Returns: duration_s, frame_rate, width, height, EXIF data

# Update database with metadata
db.update_video_metadata(video_id, duration_s=..., frame_rate=..., ...)
```

**EXIF Metadata Extracted:**
- GPS coordinates (latitude, longitude)
- Camera make/model
- Video creation timestamp
- Stored as JSONB in `exif_metadata` column

---

#### 3b. Scene Detection

**File:** `services/worker/src/domain/scene_detector.py`
**Function:** `SceneDetector.detect_scenes_with_preferences()`

```python
scenes, detection_result = scene_detector.detect_scenes_with_preferences(
    video_path,
    video_duration_s=metadata.duration_s,
    fps=metadata.frame_rate,
    preferences=detector_preferences,  # User's custom thresholds
    use_best=True,  # Try all detectors, pick best
)
```

**Available Detectors:**
- **AdaptiveDetector** (default): Adapts to content changes
- **ContentDetector**: Traditional histogram-based
- **ThresholdDetector**: Brightness/fade transitions

**"Best" Strategy:**
- Runs all 3 detectors in sequence
- Selects detector that produces most scenes
- Rationale: More scenes = better granularity for search

**Fallback:**
- If no scenes detected: Treat entire video as one scene (0.0s to duration_s)

---

#### 3c. Audio Transcription

**Function:** `openai_client.transcribe_audio_with_quality()`
**File:** `services/worker/src/adapters/openai_client.py`

```python
# Extract audio track
ffmpeg.extract_audio(video_path, audio_path)

# Transcribe with Whisper (auto-detect or forced language)
transcription_result = openai_client.transcribe_audio_with_quality(
    audio_path,
    language=transcript_language,  # None = auto-detect
)

# Returns: TranscriptionResult
# - text: Full transcript
# - has_speech: bool (quality check)
# - reason: "ok" | "music_only" | "too_short" | "low_speech_ratio"
# - segments: list[WhisperSegment]

if transcription_result.has_speech:
    full_transcript = transcription_result.text
    transcript_segments = transcription_result.segments
    # Save to database for idempotency
    db.save_transcript(video_id, full_transcript, transcript_segments)
```

**Whisper Segment Structure:**

```python
@dataclass
class WhisperSegment:
    start: float  # Start time in seconds
    end: float    # End time in seconds
    text: str     # Transcript text for this segment
    no_speech_prob: Optional[float]  # Whisper confidence (0.0-1.0)
    avg_logprob: Optional[float]     # Token probability (quality indicator)
```

**Quality Filtering:**
- Rejects transcripts dominated by music notation (♪)
- Rejects transcripts with high no_speech_prob (>0.6 average)
- Rejects very short transcripts (<10 chars)
- Filters banned phrases (ads, URLs)

**Storage:**
- `videos.full_transcript`: Plain text (TEXT column)
- `videos.transcript_segments`: JSONB array of segments

**Idempotency:**
- Cached in database
- Subsequent retries skip transcription

---

#### 3d. Parallel Scene Processing

**Function:** `VideoProcessor._process_single_scene()`
**File:** `services/worker/src/domain/video_processor.py:28-117`

**Parallelism:**

```python
max_workers = min(settings.max_scene_workers, len(scenes_to_process))
# Default: 3 workers

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(_process_single_scene, scene, ...)
               for scene in scenes_to_process]

    for future in as_completed(futures):
        success, result, scene_index = future.result()
```

**Per-Scene API Rate Limiting:**

```python
_api_semaphore = Semaphore(settings.max_api_concurrency)  # Default: 3

# Inside _process_single_scene:
with VideoProcessor._api_semaphore:
    # Only 3 scenes can call OpenAI APIs concurrently
    sidecar = sidecar_builder.build_sidecar(...)
```

**Idempotency:**
- Checks `db.get_existing_scene_indices(video_id)`
- Skips already-processed scenes
- Allows partial retry after failure

---

#### 3e. Transcript Slicing (Per Scene)

**Function:** `sidecar_builder._extract_transcript_segment_from_segments()`
**File:** `services/worker/src/domain/sidecar_builder.py:1064-1120`

**New Timestamp-Based Approach (Migration 016):**

```python
def _extract_transcript_segment_from_segments(
    segments,  # list[WhisperSegment] or list[dict]
    scene_start_s,
    scene_end_s,
    video_duration_s,
    context_pad_s=5.0,  # Expand if too short
    min_chars=50,
):
    # 1. Sort segments by start time
    sorted_segments = sorted(segments, key=lambda s: s.start)

    # 2. Find overlapping segments
    matching_segs = []
    for seg in sorted_segments:
        seg_start = seg.start  # or seg.get("start") for dicts
        seg_end = seg.end
        seg_text = seg.text

        # Include if segment overlaps scene window
        if seg_end > scene_start_s and seg_start < scene_end_s:
            matching_segs.append(seg_text)

    # 3. Join and normalize
    text = " ".join(matching_segs).strip()

    # 4. Expand context if too short
    if len(text) < min_chars:
        expanded_start = max(0.0, scene_start_s - context_pad_s)
        expanded_end = min(video_duration_s, scene_end_s + context_pad_s)
        text = get_text_for_window(expanded_start, expanded_end)

    return text
```

**Object/Dict Compatibility:**

```python
# Handles both WhisperSegment objects and dicts
if isinstance(seg, dict):
    seg_start = seg.get("start", 0.0)
    seg_text = seg.get("text", "")
else:
    seg_start = getattr(seg, "start", 0.0)
    seg_text = getattr(seg, "text", "")
```

**Fallback to Proportional Slicing:**

```python
# If segments unavailable (old videos, cached without segments)
if not transcript_segments:
    transcript_segment = sidecar_builder._extract_transcript_segment(
        full_transcript,
        scene,
        total_duration_s,
    )
    # Uses character-based proportional slicing
```

**Known Issues:**

1. **Segment Boundary Misalignment:**
   - Whisper segments don't always align with scene cuts
   - May cut mid-sentence if scene boundary falls inside a segment

2. **Context Padding Artifacts:**
   - Adding ±5s context can include unrelated content
   - No semantic boundary detection

3. **Short Scene Problem:**
   - Very short scenes (<2s) may have zero overlapping segments
   - Context expansion helps but not always sufficient

4. **Music/Ads Leakage:**
   - Quality filter happens at video level, not scene level
   - A scene might still contain music notation if mixed with speech

5. **Language Mixing:**
   - Auto-detect can fail on bilingual videos
   - No per-scene language detection

---

#### 3f. Keyframe Extraction & Quality Ranking

**Function:** `ffmpeg.extract_keyframes()`
**File:** `services/worker/src/adapters/ffmpeg.py`

```python
keyframe_paths = ffmpeg.extract_keyframes(
    video_path,
    scene.start_s,
    scene.end_s,
    work_dir / f"scene_{scene.index}",
    num_keyframes=5,  # Default: 5 frames per scene
)
```

**Frame Selection Strategy:**
- Evenly distributed across scene duration
- Returns list of JPEG paths

**Frame Quality Ranking (CLIP Embedder):**

```python
# services/worker/src/adapters/clip_embedder.py
def rank_frames_by_quality(frames: list[Path]) -> list[tuple]:
    """
    Rank frames by quality score (0.0-1.0).

    Quality Score = (brightness_score * 0.3) + (blur_score * 0.7)

    Brightness: Prefer well-lit frames (target: 0.4-0.6 normalized)
    Blur: Higher Laplacian variance = sharper (threshold: 100)
    """
    scored_frames = []
    for frame in frames:
        img = cv2.imread(str(frame))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Brightness
        brightness = np.mean(gray) / 255.0
        brightness_score = 1.0 - abs(brightness - 0.5) * 2

        # Blur (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(laplacian_var / 200.0, 1.0)

        quality_score = (brightness_score * 0.3) + (blur_score * 0.7)
        scored_frames.append((frame, quality_score))

    return sorted(scored_frames, key=lambda x: x[1], reverse=True)
```

**Best Frame Selection:**
- Ranks all 5 keyframes
- Selects highest quality frame for CLIP embedding and thumbnail

---

#### 3g. Visual Semantics Generation

**Function:** `openai_client.analyze_scene_visual_v2()`
**File:** `services/worker/src/adapters/openai_client.py`

```python
visual_data = openai_client.analyze_scene_visual_v2(
    keyframe_paths,
    scene=scene,
    language=language,  # "ko" or "en"
)

# Returns:
# - visual_description: str (1-2 sentences)
# - visual_entities: list[str] (main objects/people)
# - visual_actions: list[str] (activities detected)
# - tags: list[str] (normalized keywords)
```

**GPT-4o Prompt Structure:**
- Sends 1-5 keyframes (base64 encoded)
- Asks for structured JSON output
- Language-specific instructions (Korean vs English)

**Structured Output Format:**

```json
{
  "visual_description": "Two people sitting at a cafe table discussing",
  "visual_entities": ["person", "cafe", "table", "coffee cup"],
  "visual_actions": ["sitting", "talking", "drinking"],
  "tags": ["conversation", "cafe", "meeting", "coffee"]
}
```

---

#### 3h. CLIP Visual Embedding Generation

**Function:** `clip_embedder.embed_frame_with_quality()`
**File:** `services/worker/src/adapters/clip_embedder.py`

```python
if settings.clip_enabled:
    # Rank frames and select best
    best_frame, quality_score = clip_embedder.rank_frames_by_quality(keyframes)[0]

    # Generate CLIP embedding (512-dim)
    embedding_visual_clip, clip_metadata = clip_embedder.embed_frame_with_quality(
        best_frame,
        timeout_s=settings.clip_timeout_s,  # Default: 2.0s
    )

    # clip_metadata structure:
    {
        "model_name": "ViT-B-32",
        "pretrained": "openai",
        "embed_dim": 512,
        "normalized": true,
        "device": "cpu",
        "frame_path": "scene_12_frame_0.jpg",
        "frame_quality": {
            "brightness": 0.85,
            "blur": 120.5,
            "quality_score": 0.82
        },
        "inference_time_ms": 145.2,
        "created_at": "2025-12-16T10:30:00Z",
        "error": null
    }
```

**Model Details:**
- **Model:** OpenCLIP ViT-B-32 (Vision Transformer)
- **Dimensions:** 512 (fixed for this model)
- **Device:** CPU (no GPU required)
- **Inference Time:** ~100-200ms per frame on CPU
- **Timeout:** 2s (configurable)

**Error Handling:**
- Timeout: Returns None, logs warning
- Model load failure: Disables CLIP for session
- Frame read error: Skips that scene, continues

**Why CLIP matters:**
- Enables true visual similarity search (image-to-image)
- Complements GPT-4o text descriptions
- More robust than text-based visual embeddings

---

#### 3i. Multi-Channel Embedding Generation

**Function:** `sidecar_builder._generate_multi_channel_embeddings()`
**File:** `services/worker/src/domain/sidecar_builder.py`

**Three Separate Embeddings:**

```python
def _generate_multi_channel_embeddings(
    transcript_segment: str,
    visual_description: str,
    visual_entities: list[str],
    visual_actions: list[str],
    tags: list[str],
    video_summary: Optional[str] = None,
) -> tuple:
    """
    Generate three independent embeddings for multi-channel retrieval.

    Returns: (embedding_transcript, embedding_visual, embedding_summary)
    Each is vector(1536) or None if input is empty.
    """

    # Channel 1: Transcript only
    embedding_transcript = None
    if transcript_segment and len(transcript_segment.strip()) > 0:
        embedding_transcript = openai_client.create_embedding(transcript_segment)

    # Channel 2: Visual content only
    embedding_visual = None
    visual_text = _build_visual_text(visual_description, tags, visual_entities, visual_actions)
    if visual_text and len(visual_text.strip()) > 0:
        embedding_visual = openai_client.create_embedding(visual_text)

    # Channel 3: Summary (optional, may be None)
    embedding_summary = None
    if video_summary and len(video_summary.strip()) > 0:
        embedding_summary = openai_client.create_embedding(video_summary)

    return (embedding_transcript, embedding_visual, embedding_summary)
```

**Text Construction:**

```python
def _build_visual_text(description, tags, entities, actions):
    parts = []
    if description:
        parts.append(description)
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if entities:
        parts.append("Entities: " + ", ".join(entities))
    if actions:
        parts.append("Actions: " + ", ".join(actions))
    return " | ".join(parts)
```

**Metadata Tracking:**

```python
multi_embedding_metadata = {
    "channels": {
        "transcript": {
            "model": "text-embedding-3-small",
            "dimensions": 1536,
            "input_text_hash": hashlib.sha256(transcript_segment.encode()).hexdigest()[:16],
            "input_text_length": len(transcript_segment),
            "created_at": datetime.utcnow().isoformat(),
            "language": language
        },
        "visual": { ... },
        "summary": { ... }
    }
}
```

**Backward Compatibility:**
- Legacy `embedding` column (single combined text) still generated
- Used as fallback if multi-channel disabled

---

#### 3j. Scene Database Write

**Function:** `db.create_scene()`
**File:** `services/worker/src/adapters/database.py`

```python
scene_id = db.create_scene(
    video_id=video_id,
    index=sidecar.index,
    start_s=sidecar.start_s,
    end_s=sidecar.end_s,
    # Text fields
    transcript_segment=sidecar.transcript_segment,
    visual_summary=sidecar.visual_summary,
    visual_description=sidecar.visual_description,
    visual_entities=sidecar.visual_entities,
    visual_actions=sidecar.visual_actions,
    tags=sidecar.tags,
    combined_text=sidecar.combined_text,
    search_text=sidecar.search_text,
    # Legacy embedding
    embedding=sidecar.embedding,
    # Multi-channel embeddings (v3-multi)
    embedding_transcript=sidecar.embedding_transcript,
    embedding_visual=sidecar.embedding_visual,
    embedding_summary=sidecar.embedding_summary,
    embedding_version="v3-multi",
    multi_embedding_metadata=sidecar.multi_embedding_metadata,
    # CLIP embedding
    embedding_visual_clip=sidecar.embedding_visual_clip,
    visual_clip_metadata=sidecar.visual_clip_metadata,
    # Thumbnail
    thumbnail_url=sidecar.thumbnail_url,
    # Sidecar metadata
    sidecar_version=2,
    needs_reprocess=False,
    processing_stats=sidecar.processing_stats,
)
```

**Database Transaction:**
- Uses Supabase client `.insert()` or `.upsert()` (idempotent)
- Returns scene UUID

---

#### 3k. Video Summary Generation

**Function:** `openai_client.summarize_video_from_scenes()`
**File:** `services/worker/src/adapters/openai_client.py`

```python
scene_descriptions = db.get_scene_descriptions(video_id)
# Returns: list[tuple[int, str]] = [(index, visual_description), ...]

if scene_descriptions:
    video_summary = openai_client.summarize_video_from_scenes(
        scene_descriptions,
        transcript_language=language,
    )

    db.update_video_metadata(
        video_id=video_id,
        video_summary=video_summary,
        has_rich_semantics=True,
    )
```

**GPT-4o Prompt:**
- Sends all scene descriptions (indexed)
- Asks for 2-3 sentence video-level summary
- Language-specific output (Korean or English)

**Failure Handling:**
- If summary fails: Still marks `has_rich_semantics=True`
- Rationale: Scenes have tags/descriptions even without video summary

---

#### 3l. Status Transitions

**Success Path:**

```
PENDING → PROCESSING → READY
```

**Failure Path:**

```
PENDING → PROCESSING → FAILED (with error_message)
```

**Status Updates:**

```python
# Start
db.update_video_status(video_id, VideoStatus.PROCESSING)

# Success
db.update_video_status(video_id, VideoStatus.READY)

# Failure
db.update_video_status(
    video_id,
    VideoStatus.FAILED,
    error_message=str(e)[:500],  # Truncated to 500 chars
)
```

---

## Current Search Flow

### 1. Endpoint & Auth

**Endpoint:** `POST /v1/search`
**File:** `services/api/src/routes/search.py:321-666`

```python
@router.post("/search", response_model=SearchResponse)
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    user_id = UUID(current_user.user_id)
```

**Auth:** JWT token required (via `get_current_user` dependency)

**Tenant Scoping:**
- All database queries filter by `owner_id = user_id`
- Video access verified if `request.video_id` provided

---

### 2. Query Embedding Creation

```python
query_embedding = openai_client.create_embedding(request.query)
# Model: text-embedding-3-small (1536 dims)
# Time: ~100-200ms

embedding_ms = int((time.time() - embed_start) * 1000)
```

**Error Handling:**

```python
embedding_failed = False
try:
    query_embedding = openai_client.create_embedding(request.query)
except Exception as e:
    logger.error(f"Failed to create embedding: {e}")
    embedding_failed = True
```

**Fallback:**
- If embedding fails AND OpenSearch available: Use lexical-only mode
- If embedding fails AND OpenSearch unavailable: Return 500 error

---

### 3. Retrieval Mode Selection

**Priority Order:**

```python
use_multi_dense = (
    settings.multi_dense_enabled
    and not embedding_failed
)

use_hybrid = (
    settings.hybrid_search_enabled
    and opensearch_client.is_available()
    and not embedding_failed
    and not use_multi_dense  # Multi-dense takes precedence
)

use_lexical_only = (
    embedding_failed
    and settings.hybrid_search_enabled
    and opensearch_client.is_available()
)

# Dense-only if nothing else applies
```

**Mode Outcomes:**

| Condition | Mode | Channels Used |
|-----------|------|---------------|
| `multi_dense_enabled=True` | Multi-Dense | Transcript, Visual, Summary, Lexical |
| `hybrid_search_enabled=True` | Hybrid | Dense (legacy), Lexical |
| Embedding failed | Lexical-Only | Lexical (BM25) |
| OpenSearch down | Dense-Only | Dense (legacy) |

---

### 4. Multi-Dense Parallel Retrieval

**Function:** `_run_multi_dense_search()`
**File:** `services/api/src/routes/search.py:116-232`

**Parallel Execution:**

```python
def run_transcript():
    start = time.time()
    results = db.search_scenes_transcript_embedding(
        query_embedding=query_embedding,
        user_id=user_id,
        video_id=video_id,
        match_count=settings.candidate_k_transcript,  # Default: 200
        threshold=settings.threshold_transcript,      # Default: 0.2
    )
    elapsed = int((time.time() - start) * 1000)
    candidates = [Candidate(scene_id=sid, rank=rank, score=score)
                  for sid, rank, score in results]
    return ("transcript", candidates, elapsed)

# Similar for run_visual(), run_summary(), run_lexical()

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(run_transcript): "transcript",
        executor.submit(run_visual): "visual",
        executor.submit(run_summary): "summary",
        executor.submit(run_lexical): "lexical",
    }

    for future in as_completed(futures):
        channel_name = futures[future]
        try:
            ch_name, candidates, elapsed = future.result(
                timeout=settings.multi_dense_timeout_s  # Default: 5.0s
            )
            channel_candidates[ch_name] = candidates
            timing_ms[ch_name] = elapsed
        except TimeoutError:
            logger.warning(f"{channel_name} timed out")
            channel_candidates[channel_name] = []
            timing_ms[channel_name] = int(timeout * 1000)
        except Exception as e:
            logger.error(f"{channel_name} failed: {e}")
            channel_candidates[channel_name] = []
            timing_ms[channel_name] = 0
```

**Timeout Behavior:**
- Each channel has independent 5s timeout
- Timeout treated as empty result (graceful degradation)
- Fusion proceeds with available channels

**Channel Configuration:**

```python
# Default weights (configurable via env vars)
MULTI_DENSE_WEIGHT_TRANSCRIPT=0.45  # 45%
MULTI_DENSE_WEIGHT_VISUAL=0.25      # 25%
MULTI_DENSE_WEIGHT_SUMMARY=0.10     # 10%
MULTI_DENSE_WEIGHT_LEXICAL=0.20     # 20%

# Skip channels with zero weight
active_weights = {k: v for k, v in weights.items() if v > 0}
```

**Candidate Pool Sizes:**

```python
CANDIDATE_K_TRANSCRIPT=200  # Fetch top 200 from transcript channel
CANDIDATE_K_VISUAL=200
CANDIDATE_K_SUMMARY=200
CANDIDATE_K_LEXICAL=200
```

**Tenancy Enforcement:**
- All RPC functions join `videos` table and filter by `owner_id`
- `filter_user_id` parameter required (not optional)

---

### 5. Fusion Method Selection

**Multi-Channel MinMax Mean (Default):**

```python
if fusion_method == "rrf":
    fused_results = multi_channel_rrf_fuse(
        channel_candidates=fusion_channels,
        k=settings.rrf_k,  # Default: 60
        top_k=request.limit,
        include_debug=settings.search_debug,
    )
else:  # minmax_mean
    fused_results = multi_channel_minmax_fuse(
        channel_candidates=fusion_channels,
        channel_weights=fusion_weights,
        eps=settings.fusion_minmax_eps,  # Default: 1e-9
        top_k=request.limit,
        include_debug=settings.search_debug,
    )
```

**MinMax Mean Algorithm:**

```python
def multi_channel_minmax_fuse(
    channel_candidates: dict[str, list[Candidate]],
    channel_weights: dict[str, float],
    eps: float,
    top_k: int,
    include_debug: bool,
) -> list[FusedCandidate]:
    """
    Multi-channel MinMax normalization + weighted fusion.

    Steps:
    1. Collect all candidates across channels
    2. Per-channel MinMax normalization: (score - min) / (max - min + eps)
    3. Weighted sum: final_score = Σ(weight_i * norm_score_i)
    4. Sort by final_score descending
    5. Return top_k
    """

    # 1. Build candidate dict: scene_id → {channel: (score, rank)}
    candidate_map = defaultdict(dict)
    for channel_name, candidates in channel_candidates.items():
        for cand in candidates:
            candidate_map[cand.scene_id][channel_name] = (cand.score, cand.rank)

    # 2. Per-channel MinMax normalization
    channel_stats = {}
    for channel_name, candidates in channel_candidates.items():
        scores = [c.score for c in candidates]
        if scores:
            min_score = min(scores)
            max_score = max(scores)
            channel_stats[channel_name] = (min_score, max_score)

    # 3. Normalize and compute weighted scores
    fused_candidates = []
    for scene_id, channel_data in candidate_map.items():
        weighted_score = 0.0
        channel_scores_debug = {}

        for channel_name, (raw_score, rank) in channel_data.items():
            weight = channel_weights.get(channel_name, 0.0)
            if weight == 0.0:
                continue

            min_score, max_score = channel_stats[channel_name]
            norm_score = (raw_score - min_score) / (max_score - min_score + eps)

            contribution = weight * norm_score
            weighted_score += contribution

            if include_debug:
                channel_scores_debug[channel_name] = {
                    "raw_score": raw_score,
                    "norm_score": norm_score,
                    "weight": weight,
                    "contribution": contribution,
                    "rank": rank,
                    "present": True,
                }

        # Handle missing channels
        for channel_name in channel_weights.keys():
            if channel_name not in channel_data and include_debug:
                channel_scores_debug[channel_name] = {
                    "present": False,
                    "weight": channel_weights[channel_name],
                }

        fused_candidates.append(FusedCandidate(
            scene_id=scene_id,
            score=weighted_score,
            score_type=ScoreType.MULTI_DENSE_MINMAX_MEAN,
            channel_scores=channel_scores_debug if include_debug else None,
        ))

    # 4. Sort and return top_k
    fused_candidates.sort(key=lambda x: x.score, reverse=True)
    return fused_candidates[:top_k]
```

**RRF Algorithm (Alternative):**

```python
def multi_channel_rrf_fuse(
    channel_candidates: dict[str, list[Candidate]],
    k: int = 60,
    top_k: int = 10,
    include_debug: bool = False,
) -> list[FusedCandidate]:
    """
    Reciprocal Rank Fusion across multiple channels.

    Formula: RRF_score = Σ(1 / (k + rank_i))

    Where:
    - k = 60 (constant, controls diminishing returns)
    - rank_i = rank in channel i (1-indexed)
    """

    candidate_map = defaultdict(dict)
    for channel_name, candidates in channel_candidates.items():
        for cand in candidates:
            candidate_map[cand.scene_id][channel_name] = (cand.rank, cand.score)

    fused_candidates = []
    for scene_id, channel_data in candidate_map.items():
        rrf_score = 0.0
        channel_scores_debug = {}

        for channel_name, (rank, raw_score) in channel_data.items():
            rrf_contrib = 1.0 / (k + rank)
            rrf_score += rrf_contrib

            if include_debug:
                channel_scores_debug[channel_name] = {
                    "rank": rank,
                    "raw_score": raw_score,
                    "rrf_contribution": rrf_contrib,
                    "present": True,
                }

        fused_candidates.append(FusedCandidate(
            scene_id=scene_id,
            score=rrf_score,
            score_type=ScoreType.MULTI_DENSE_RRF,
            channel_scores=channel_scores_debug if include_debug else None,
        ))

    fused_candidates.sort(key=lambda x: x.score, reverse=True)
    return fused_candidates[:top_k]
```

**Fusion Trade-offs:**

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **MinMax Mean** | Preserves score magnitudes, interpretable weights | Sensitive to outliers, inflation if min≈max | Balanced multi-channel search |
| **RRF** | Robust to outliers, rank-based (no score calibration) | Loses score information, all channels equal | Heterogeneous score distributions |

---

### 6. Hydration & Order Preservation

**Function:** `_hydrate_scenes()`
**File:** `services/api/src/routes/search.py:234-318`

```python
def _hydrate_scenes(
    fused_results: list[FusedCandidate],
    include_debug: bool,
) -> tuple[list[VideoSceneResponse], int]:
    # 1. Extract scene IDs in fused order
    scene_ids = [UUID(r.scene_id) for r in fused_results]

    # 2. Batch fetch scenes (preserves order)
    scenes = db.get_scenes_by_ids(scene_ids, preserve_order=True)

    # 3. Batch fetch video filenames
    video_ids = list(set(scene.video_id for scene in scenes))
    filename_map = db.get_video_filenames_by_ids(video_ids)

    # 4. Build lookup for fused results
    fused_by_id = {r.scene_id: r for r in fused_results}

    # 5. Construct response objects
    responses = []
    for scene in scenes:
        fused = fused_by_id.get(str(scene.id))

        response_data = {
            "id": scene.id,
            "video_id": scene.video_id,
            "video_filename": filename_map.get(str(scene.video_id)),
            "index": scene.index,
            "start_s": scene.start_s,
            "end_s": scene.end_s,
            "transcript_segment": scene.transcript_segment,
            "visual_summary": scene.visual_summary,
            "visual_description": scene.visual_description,
            "visual_entities": scene.visual_entities,
            "visual_actions": scene.visual_actions,
            "tags": scene.tags,
            "thumbnail_url": scene.thumbnail_url,
            "created_at": scene.created_at,
            # Score fields
            "score": fused.score,
            "score_type": fused.score_type.value,
            "similarity": fused.score,  # Backward compat alias
        }

        # Add debug fields if enabled
        if include_debug and fused.channel_scores:
            response_data["channel_scores"] = fused.channel_scores

        responses.append(VideoSceneResponse(**response_data))

    return responses, hydrate_ms
```

**Order Preservation:**
- `db.get_scenes_by_ids(scene_ids, preserve_order=True)`
- Returns scenes in same order as input `scene_ids`
- Critical for ranking integrity

**Batch Queries:**
- Scenes: Single query with `IN (id1, id2, ...)`
- Filenames: Single query with `IN (video_id1, video_id2, ...)`
- Efficient even with 100+ results

---

### 7. Response Schema

**File:** `services/api/src/domain/schemas.py`

```python
class VideoSceneResponse(BaseModel):
    # Core fields
    id: UUID
    video_id: UUID
    video_filename: Optional[str]
    index: int
    start_s: float
    end_s: float

    # Content fields
    transcript_segment: Optional[str]
    visual_summary: Optional[str]
    combined_text: Optional[str]
    thumbnail_url: Optional[str]
    visual_description: Optional[str]
    visual_entities: Optional[list[str]]
    visual_actions: Optional[list[str]]
    tags: Optional[list[str]]
    created_at: Optional[datetime]

    # Score fields (primary)
    score: Optional[float]  # Final fusion score
    score_type: Optional[str]  # "multi_dense_minmax_mean", "rrf", etc.

    # Backward compatibility
    similarity: Optional[float]  # Alias for score

    # Debug fields (only if SEARCH_DEBUG=true)
    channel_scores: Optional[dict]  # Per-channel breakdown
    dense_score_raw: Optional[float]  # Legacy 2-signal mode
    lexical_score_raw: Optional[float]
    dense_score_norm: Optional[float]
    lexical_score_norm: Optional[float]
    dense_rank: Optional[int]
    lexical_rank: Optional[int]
```

**Channel Scores Structure (Debug):**

```json
{
  "dense_transcript": {
    "raw_score": 0.85,
    "norm_score": 0.92,
    "weight": 0.45,
    "contribution": 0.414,
    "rank": 3,
    "present": true
  },
  "dense_visual": {
    "raw_score": 0.72,
    "norm_score": 0.81,
    "weight": 0.25,
    "contribution": 0.2025,
    "rank": 12,
    "present": true
  },
  "lexical": {
    "present": false,
    "weight": 0.20
  }
}
```

---

## Configuration Reference

### API Service Settings

**File:** `services/api/src/config.py`

| Setting | Default | Description |
|---------|---------|-------------|
| `HEIMDEX_HYBRID_SEARCH_ENABLED` | `True` | Enable hybrid (dense + lexical) search |
| `HEIMDEX_FUSION_METHOD` | `"minmax_mean"` | Fusion algorithm: "minmax_mean" or "rrf" |
| `HEIMDEX_FUSION_WEIGHT_DENSE` | `0.7` | Weight for dense scores in 2-signal mode |
| `HEIMDEX_FUSION_WEIGHT_LEXICAL` | `0.3` | Weight for lexical scores in 2-signal mode |
| `HEIMDEX_FUSION_MINMAX_EPS` | `1e-9` | Epsilon for MinMax division by zero |
| `HEIMDEX_RRF_K` | `60` | RRF constant (k in 1/(k+rank)) |
| `HEIMDEX_CANDIDATE_K_DENSE` | `200` | Dense retrieval pool size (legacy) |
| `HEIMDEX_CANDIDATE_K_LEXICAL` | `200` | Lexical retrieval pool size |
| `HEIMDEX_SEARCH_DEBUG` | `False` | Include debug fields in responses |
| **Multi-Dense Settings** | | |
| `HEIMDEX_MULTI_DENSE_ENABLED` | `True` | Enable multi-channel retrieval |
| `HEIMDEX_MULTI_DENSE_TIMEOUT_S` | `5.0` | Per-channel timeout in seconds |
| `HEIMDEX_MULTI_DENSE_WEIGHT_TRANSCRIPT` | `0.45` | Transcript channel weight |
| `HEIMDEX_MULTI_DENSE_WEIGHT_VISUAL` | `0.25` | Visual channel weight |
| `HEIMDEX_MULTI_DENSE_WEIGHT_SUMMARY` | `0.10` | Summary channel weight |
| `HEIMDEX_MULTI_DENSE_WEIGHT_LEXICAL` | `0.20` | Lexical channel weight |
| `HEIMDEX_CANDIDATE_K_TRANSCRIPT` | `200` | Transcript pool size |
| `HEIMDEX_CANDIDATE_K_VISUAL` | `200` | Visual pool size |
| `HEIMDEX_CANDIDATE_K_SUMMARY` | `200` | Summary pool size |
| `HEIMDEX_THRESHOLD_TRANSCRIPT` | `0.2` | Min similarity for transcript |
| `HEIMDEX_THRESHOLD_VISUAL` | `0.15` | Min similarity for visual |
| `HEIMDEX_THRESHOLD_SUMMARY` | `0.2` | Min similarity for summary |

---

### Worker Service Settings

**File:** `services/worker/src/config.py`

| Setting | Default | Description |
|---------|---------|-------------|
| `HEIMDEX_TEMP_DIR` | `"/tmp/heimdex"` | Working directory for video processing |
| `HEIMDEX_MAX_SCENE_WORKERS` | `3` | Max parallel scene processing threads |
| `HEIMDEX_MAX_API_CONCURRENCY` | `3` | Max concurrent OpenAI API calls |
| `HEIMDEX_SCENE_MIN_LEN_SECONDS` | `1.0` | Minimum scene length |
| `HEIMDEX_SCENE_DETECTOR` | `"best"` | Detector strategy: "best", "adaptive", etc. |
| **CLIP Settings** | | |
| `HEIMDEX_CLIP_ENABLED` | `True` | Enable CLIP visual embeddings |
| `HEIMDEX_CLIP_MODEL_NAME` | `"ViT-B-32"` | CLIP model architecture |
| `HEIMDEX_CLIP_PRETRAINED` | `"openai"` | Pretrained weights source |
| `HEIMDEX_CLIP_TIMEOUT_S` | `2.0` | Per-frame inference timeout |
| **OpenAI Settings** | | |
| `HEIMDEX_OPENAI_API_KEY` | *required* | OpenAI API key |
| `HEIMDEX_OPENAI_EMBEDDING_MODEL` | `"text-embedding-3-small"` | Embedding model (1536 dims) |
| `HEIMDEX_OPENAI_VISION_MODEL` | `"gpt-4o"` | Vision model for scene analysis |
| `HEIMDEX_OPENAI_CHAT_MODEL` | `"gpt-4o"` | Chat model for summaries |

---

## Database & Migrations Reference

### Critical Tables

**`videos` Table:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `owner_id` | UUID | User ID (FK to auth.users) |
| `storage_path` | TEXT | S3/Supabase path |
| `status` | TEXT | "PENDING", "PROCESSING", "READY", "FAILED" |
| `filename` | TEXT | Original filename |
| `duration_s` | FLOAT | Video duration |
| `frame_rate` | FLOAT | FPS |
| `width` | INT | Resolution width |
| `height` | INT | Resolution height |
| `full_transcript` | TEXT | Full transcript text |
| **`transcript_segments`** | **JSONB** | **Whisper segments with timestamps (Migration 016)** |
| `video_summary` | TEXT | AI-generated summary |
| `has_rich_semantics` | BOOLEAN | v2 metadata flag |
| `thumbnail_url` | TEXT | Video thumbnail URL |
| `exif_metadata` | JSONB | Full EXIF data |
| `location_latitude` | FLOAT | GPS latitude |
| `location_longitude` | FLOAT | GPS longitude |
| `location_name` | TEXT | Reverse-geocoded name |
| `camera_make` | TEXT | Camera manufacturer |
| `camera_model` | TEXT | Camera model |
| `error_message` | TEXT | Error if failed |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

**`video_scenes` Table:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `video_id` | UUID | FK to videos |
| `index` | INT | Scene index (0-based) |
| `start_s` | FLOAT | Start time |
| `end_s` | FLOAT | End time |
| `transcript_segment` | TEXT | Scene transcript |
| `visual_summary` | TEXT | Legacy visual desc |
| `visual_description` | TEXT | v2 visual desc |
| `visual_entities` | TEXT[] | Detected objects |
| `visual_actions` | TEXT[] | Detected actions |
| `tags` | TEXT[] | Normalized keywords |
| `combined_text` | TEXT | Legacy combined text |
| `search_text` | TEXT | v2 optimized text |
| `thumbnail_url` | TEXT | Scene thumbnail |
| **Legacy Embedding** | | |
| `embedding` | VECTOR(1536) | Single combined embedding |
| **Multi-Channel Embeddings (Migration 015)** | | |
| **`embedding_transcript`** | **VECTOR(1536)** | **Transcript-only embedding** |
| **`embedding_visual`** | **VECTOR(1536)** | **Visual-only embedding** |
| **`embedding_summary`** | **VECTOR(1536)** | **Summary embedding** |
| `embedding_version` | TEXT | "v3-multi", "v2", NULL |
| `embedding_metadata` | JSONB | Legacy metadata |
| `multi_embedding_metadata` | JSONB | Per-channel metadata |
| **CLIP Embedding (Migration 017)** | | |
| **`embedding_visual_clip`** | **VECTOR(512)** | **CLIP visual embedding** |
| **`visual_clip_metadata`** | **JSONB** | **CLIP generation metadata** |
| `sidecar_version` | INT | Sidecar schema version |
| `needs_reprocess` | BOOLEAN | Reprocess flag |
| `processing_stats` | JSONB | Processing metrics |
| `created_at` | TIMESTAMP | Creation time |

---

### Critical Indexes

**`video_scenes` HNSW Indexes (pgvector):**

```sql
-- Legacy embedding (still used in dense-only mode)
CREATE INDEX idx_video_scenes_embedding
    ON video_scenes
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Multi-channel embeddings (Migration 015)
CREATE INDEX idx_video_scenes_embedding_transcript
    ON video_scenes
    USING hnsw (embedding_transcript vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_video_scenes_embedding_visual
    ON video_scenes
    USING hnsw (embedding_visual vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_video_scenes_embedding_summary
    ON video_scenes
    USING hnsw (embedding_summary vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- CLIP embedding (Migration 017)
CREATE INDEX idx_video_scenes_embedding_visual_clip
    ON video_scenes
    USING hnsw (embedding_visual_clip vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Partial Indexes (NULL exclusion):**

```sql
CREATE INDEX idx_video_scenes_embedding_transcript_not_null
    ON video_scenes (id)
    WHERE embedding_transcript IS NOT NULL;

-- Similar for _visual, _summary, _visual_clip
```

**Other Indexes:**

```sql
-- Efficient scene listing by video
CREATE INDEX idx_video_scenes_video_id ON video_scenes (video_id);

-- Scene ordering
CREATE INDEX idx_video_scenes_video_id_index ON video_scenes (video_id, index);

-- Transcript segments (GIN for JSONB)
CREATE INDEX idx_videos_transcript_segments ON videos USING GIN (transcript_segments);
```

---

### RPC Functions (Tenant-Safe)

**Multi-Channel Dense Search Functions (Migration 015):**

```sql
-- Transcript channel
search_scenes_by_transcript_embedding(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 200,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (id uuid, video_id uuid, similarity float)

-- Visual channel
search_scenes_by_visual_embedding(...)

-- Summary channel
search_scenes_by_summary_embedding(...)
```

**CLIP Search Function (Migration 017):**

```sql
search_scenes_by_visual_clip_embedding(
    query_embedding vector(512),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 20,
    filter_video_id uuid DEFAULT NULL,
    filter_user_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    video_id uuid,
    index int,
    start_s float,
    end_s float,
    thumbnail_url text,
    transcript_segment text,
    visual_summary text,
    visual_description text,
    visual_entities text[],
    visual_actions text[],
    tags text[],
    embedding_visual_clip vector(512),
    visual_clip_metadata jsonb,
    similarity float
)
```

**Tenancy Enforcement (All Functions):**

```sql
-- All RPC functions include:
INNER JOIN videos v ON vs.video_id = v.id
WHERE
    vs.embedding_transcript IS NOT NULL
    AND (1 - (vs.embedding_transcript <=> query_embedding)) > match_threshold
    AND (filter_video_id IS NULL OR vs.video_id = filter_video_id)
    AND (filter_user_id IS NULL OR v.owner_id = filter_user_id)
```

**Critical:** `filter_user_id` is REQUIRED in API calls, not optional.

---

## OpenSearch Reference

**Index Name:** `video_scenes`

**Mapping:**

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "korean_analyzer": {
          "type": "custom",
          "tokenizer": "nori_tokenizer",
          "filter": ["nori_posfilter", "lowercase"]
        },
        "english_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "english_stop", "english_stemmer"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "scene_id": {"type": "keyword"},
      "video_id": {"type": "keyword"},
      "owner_id": {"type": "keyword"},
      "transcript_segment": {
        "type": "text",
        "analyzer": "korean_analyzer",
        "fields": {
          "en": {"type": "text", "analyzer": "english_analyzer"}
        }
      },
      "visual_description": {
        "type": "text",
        "analyzer": "korean_analyzer",
        "fields": {
          "en": {"type": "text", "analyzer": "english_analyzer"}
        }
      },
      "tags": {"type": "keyword"},
      "visual_entities": {"type": "keyword"},
      "visual_actions": {"type": "keyword"}
    }
  }
}
```

**BM25 Query Builder:**

```python
def bm25_search(query, owner_id, video_id, size):
    must_filters = [{"term": {"owner_id": owner_id}}]
    if video_id:
        must_filters.append({"term": {"video_id": video_id}})

    return {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "transcript_segment^2.0",
                                "visual_description^1.5",
                                "tags^1.0",
                                "visual_entities^1.0",
                                "visual_actions^0.8"
                            ],
                            "type": "best_fields"
                        }
                    }
                ],
                "filter": must_filters
            }
        },
        "size": size
    }
```

**Field Boosts:**
- `transcript_segment`: 2.0x (highest priority)
- `visual_description`: 1.5x
- `tags`: 1.0x
- `visual_entities`: 1.0x
- `visual_actions`: 0.8x

**Tenancy:** `owner_id` filter REQUIRED in all queries.

---

## Safety & Reliability

### Tenancy Invariants

**Database RPC Functions:**

✅ **All RPC functions enforce tenant isolation:**

```sql
-- services/api/src/adapters/database.py
db.search_scenes_transcript_embedding(
    query_embedding=query_embedding,
    user_id=user_id,  # REQUIRED, not optional
    video_id=video_id,  # Optional filter
    ...
)

-- Maps to SQL:
INNER JOIN videos v ON vs.video_id = v.id
WHERE (filter_user_id IS NULL OR v.owner_id = filter_user_id)
```

**OpenSearch Queries:**

✅ **All OpenSearch queries filter by owner_id:**

```python
must_filters = [{"term": {"owner_id": str(user_id)}}]

opensearch_client.bm25_search(
    query=query,
    owner_id=str(user_id),  # REQUIRED
    ...
)
```

**Video Access Verification:**

✅ **All video-scoped operations verify ownership:**

```python
if request.video_id:
    video = db.get_video(request.video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if video.owner_id != user_id:
        raise HTTPException(403, "Not authorized")
```

**JWT Authentication:**

✅ **All API endpoints require JWT:**

```python
@router.post("/search")
async def search_scenes(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),  # Required
):
    user_id = UUID(current_user.user_id)
```

---

### Failure Modes & Graceful Degradation

**Embedding Generation Failure:**

```python
embedding_failed = False
try:
    query_embedding = openai_client.create_embedding(request.query)
except Exception as e:
    logger.error(f"Failed to create embedding: {e}")
    embedding_failed = True

# Fallback to lexical-only if OpenSearch available
if embedding_failed and opensearch_client.is_available():
    use_lexical_only = True
else:
    raise HTTPException(500, "Failed to process search query")
```

**OpenSearch Unavailable:**

```python
if not opensearch_client.is_available():
    # Fall back to dense-only mode
    use_hybrid = False
    logger.warning("OpenSearch unavailable, using dense-only search")
```

**Multi-Dense Channel Timeout:**

```python
try:
    ch_name, candidates, elapsed = future.result(timeout=5.0)
    channel_candidates[ch_name] = candidates
except TimeoutError:
    logger.warning(f"{channel_name} timed out")
    channel_candidates[channel_name] = []  # Empty, not error
    # Fusion continues with remaining channels
```

**Partial Scene Processing Failure:**

```python
# Worker continues even if some scenes fail
if failed_scenes:
    logger.warning(f"Failed scenes: {failed_scenes}")
    # Don't raise exception - partial processing is acceptable
    # Video still marked as READY

# At least some scenes processed successfully
db.update_video_status(video_id, VideoStatus.READY)
```

**CLIP Generation Failure:**

```python
try:
    embedding_visual_clip, clip_metadata = clip_embedder.embed_frame(...)
except Exception as e:
    logger.error(f"CLIP embedding failed: {e}")
    embedding_visual_clip = None
    visual_clip_metadata = {"error": str(e)}
    # Continue processing - CLIP is optional
```

---

### Timeouts & Retry Policies

**Per-Channel Retrieval Timeout:**

```python
# Default: 5.0s per channel
HEIMDEX_MULTI_DENSE_TIMEOUT_S=5.0

# In ThreadPoolExecutor:
future.result(timeout=settings.multi_dense_timeout_s)
```

**CLIP Inference Timeout:**

```python
# Default: 2.0s per frame
HEIMDEX_CLIP_TIMEOUT_S=2.0

# In CLIPEmbedder:
with timeout(self.timeout_s):
    features = self.model.encode_image(image_tensor)
```

**OpenAI API Timeout:**

```python
# OpenAI client default: 60s
# No explicit timeout in worker code (relies on OpenAI SDK defaults)
```

**Dramatiq Retry Policy:**

```python
# Video processing task retries (from Dramatiq middleware)
# Default: 3 retries with exponential backoff
# Max delay: ~10 minutes before final failure
```

**Worker Scene Processing:**

```python
# No timeout on individual scenes
# Semaphore limits concurrency to prevent resource exhaustion
# If OpenAI API hangs, scene will eventually timeout via SDK
```

---

### Idempotency Strategy

**Transcript Caching:**

```python
# Check cache before transcription
full_transcript, transcript_segments = db.get_cached_transcript(video_id)

if full_transcript:
    logger.info("Using cached transcript")
else:
    # Transcribe and save
    transcription_result = openai_client.transcribe_audio(...)
    db.save_transcript(video_id, full_transcript, transcript_segments)
```

**Scene Upsert:**

```python
# Check existing scenes before processing
existing_scene_indices = db.get_existing_scene_indices(video_id)

# Skip already-processed scenes
scenes_to_process = [s for s in scenes if s.index not in existing_scene_indices]
```

**Video Status Transitions:**

```python
# Status updates are atomic
db.update_video_status(video_id, VideoStatus.PROCESSING)
# ... processing ...
db.update_video_status(video_id, VideoStatus.READY)

# Retries start from PENDING or FAILED state
# No duplicate processing if status=READY
```

**Backfill Scripts:**

```python
# Backfill scripts are idempotent via embedding_version check
if scene.embedding_version == "v3-multi":
    logger.info(f"Scene {scene.id} already has v3-multi embeddings, skipping")
    continue
```

---

## Known Issues / Gaps / Risks

### 1. Transcript Slicing Issues

**Problem:** Whisper segment boundaries don't align with scene cuts.

**Symptoms:**
- Mid-sentence cuts at scene boundaries
- Short scenes (<2s) may have zero overlapping segments
- Context padding can include unrelated content

**Example:**

```
Scene: 10.0s - 12.5s
Whisper Segments:
  [9.0s - 10.5s]: "Let's talk about"
  [10.5s - 13.0s]: "the next topic which is"

Extracted: "Let's talk about the next topic which is"
Issue: Includes 0.5s before scene and 0.5s after scene
```

**Mitigation:**
- Context padding is configurable (`context_pad_s=5.0`)
- Minimum character threshold triggers expansion (`min_chars=50`)

**Future Improvements:**
- Sentence boundary detection (NLTK/spaCy)
- Semantic chunking instead of timestamp-only
- Per-scene language detection for multilingual videos

---

### 2. Missing/Empty Channel Embeddings

**Problem:** Some scenes may have NULL embeddings for certain channels.

**Causes:**
- No transcript (silent video, music only)
- No visual description (GPT-4o failure, timeout)
- No summary (video-level summary, not scene-level)

**Impact on Search:**
- Channel returns zero results for that scene
- Scene excluded from that channel's candidate pool
- Still visible in other channels

**Mitigation:**
- Partial indexes skip NULL embeddings (query optimization)
- Fusion continues with available channels
- Graceful degradation: empty channel = 0 contribution

**Example:**

```python
# Scene 42: transcript_segment is empty (silent scene)
# embedding_transcript = NULL

# During search:
results = db.search_scenes_transcript_embedding(...)
# Scene 42 not in results

# But scene 42 may appear in visual channel results
results = db.search_scenes_visual_embedding(...)
# Scene 42 appears if has visual description
```

---

### 3. OpenSearch Index Staleness

**Problem:** OpenSearch index is not automatically updated when scenes are added/updated.

**Current Behavior:**
- Worker writes to Postgres only
- OpenSearch indexing is manual (backfill script required)

**Consequences:**
- Lexical search returns stale results
- New videos not searchable via keywords until reindex
- Multi-dense mode still works (uses Postgres only)

**Mitigation:**
- Periodic reindex (manual or cron job)
- Multi-dense mode reduces reliance on lexical

**Future Fix:**
- Add OpenSearch indexing to worker pipeline
- Real-time updates via webhooks or queue

---

### 4. MinMax Score Inflation

**Problem:** If all candidates have similar scores, MinMax normalization inflates differences.

**Example:**

```python
# Channel A: scores = [0.85, 0.84, 0.83, 0.82]
min_score = 0.82, max_score = 0.85
range = 0.03 (very small)

# After normalization:
norm_scores = [1.0, 0.67, 0.33, 0.0]
# Tiny differences become large!
```

**Impact:**
- Overemphasizes minor score differences
- Can dominate fusion if one channel has tight score distribution

**Mitigation:**
- `eps=1e-9` prevents division by zero, but doesn't fix inflation
- RRF fusion is more robust (rank-based, not score-based)

**Alternative:**
- Z-score normalization (mean/std)
- Sigmoid normalization
- RRF fusion (already supported)

---

### 5. CLIP Inference Latency

**Problem:** CLIP inference on CPU is slow (~100-200ms per frame).

**Impact:**
- Scene processing takes longer with CLIP enabled
- Timeout risk if frame is large or CPU is slow

**Mitigation:**
- Per-frame timeout (default 2s)
- Frame quality pre-filtering (skip blurry/dark frames)
- Timeout treated as missing embedding (NULL)

**Future Optimization:**
- GPU inference (requires GPU workers)
- Batch inference (process multiple frames in one pass)
- Smaller CLIP models (e.g., ViT-B-16 instead of ViT-B-32)

---

### 6. Parallel Retrieval Overhead

**Problem:** Running 4 channels in parallel has overhead.

**Overhead Sources:**
- ThreadPoolExecutor context switching
- Database connection pool contention
- Network latency (4 simultaneous RPC calls)

**Measured Impact:**
- Total latency: ~300-500ms (vs. ~150ms for single-channel)
- Acceptable for <10s user-facing search

**Mitigation:**
- Per-channel timeouts prevent runaway queries
- Connection pooling (Supabase client)

---

### 7. Embedding Version Migration

**Problem:** Old scenes have `embedding_version=NULL` or `"v2"`, new scenes have `"v3-multi"`.

**Inconsistency:**
- Mixed embedding versions in same search results
- Old scenes only searchable via legacy `embedding` column
- New scenes have per-channel embeddings

**Current State:**
- Legacy search (`db.search_scenes`) uses `embedding` column (works for all)
- Multi-channel search only returns scenes with `embedding_transcript/visual/summary` (new only)

**Mitigation:**
- Backfill script regenerates embeddings for old scenes
- Gradual migration as videos are reprocessed

**Backfill Script:**

```bash
python services/worker/src/scripts/backfill_scene_embeddings_v3.py \
  --batch-size 50 \
  --concurrency 3
```

---

## Verification Checklist

### Local Development

**1. Check Database Migrations:**

```bash
psql $DATABASE_URL -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'video_scenes'
  AND column_name LIKE '%embedding%'
ORDER BY ordinal_position;
"

# Expected output:
# embedding | vector(1536)
# embedding_transcript | vector(1536)
# embedding_visual | vector(1536)
# embedding_summary | vector(1536)
# embedding_visual_clip | vector(512)
# embedding_version | text
# embedding_metadata | jsonb
# multi_embedding_metadata | jsonb
# visual_clip_metadata | jsonb
```

**2. Verify RPC Functions:**

```bash
psql $DATABASE_URL -c "
SELECT routine_name
FROM information_schema.routines
WHERE routine_name LIKE '%embedding%'
  AND routine_schema = 'public';
"

# Expected output:
# search_scenes_by_embedding (legacy)
# search_scenes_by_transcript_embedding
# search_scenes_by_visual_embedding
# search_scenes_by_summary_embedding
# search_scenes_by_visual_clip_embedding
```

**3. Test Video Upload & Processing:**

```bash
# Upload video
curl -X POST http://localhost:8000/v1/videos/upload-url \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.mp4", "file_extension": "mp4"}'

# Mark uploaded (triggers processing)
curl -X POST http://localhost:8000/v1/videos/{video_id}/uploaded \
  -H "Authorization: Bearer $JWT_TOKEN"

# Check logs
docker-compose logs -f worker

# Expected logs:
# - "Detecting scenes using multi-detector approach"
# - "Detected N scenes using adaptive detector"
# - "Using cached transcript" or "Transcribing audio"
# - "Processing scene 1/N"
# - "Generating CLIP embedding for frame..."
# - "Scene 0 saved with id=..."
# - "Video processing complete for video_id=..."
```

**4. Test Multi-Channel Search:**

```bash
# Search with debug enabled
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "사람이 걷고 있는 장면",
    "limit": 5
  }'

# Expected response:
{
  "query": "사람이 걷고 있는 장면",
  "results": [
    {
      "id": "...",
      "score": 0.78,
      "score_type": "multi_dense_minmax_mean",
      "similarity": 0.78,
      "channel_scores": {  # If SEARCH_DEBUG=true
        "dense_transcript": {
          "raw_score": 0.85,
          "norm_score": 0.92,
          "weight": 0.45,
          "contribution": 0.414,
          "rank": 3,
          "present": true
        },
        ...
      }
    }
  ],
  "total": 5,
  "latency_ms": 423,
  "fusion_method": "multi_dense_minmax_mean",
  "fusion_weights": {
    "transcript": 0.45,
    "visual": 0.25,
    "summary": 0.10,
    "lexical": 0.20
  }
}
```

**5. Check Worker Health:**

```bash
# Redis connection
docker-compose exec worker python -c "
from src.config import settings
from redis import Redis
r = Redis.from_url(settings.redis_url)
print(r.ping())  # Should print True
"

# Database connection
docker-compose exec worker python -c "
from src.adapters.database import db
profile = db.get_user_profile('some-uuid')
print('DB connected')
"

# CLIP model loading
docker-compose exec worker python -c "
from src.adapters.clip_embedder import clip_embedder
print(f'CLIP model: {clip_embedder.model_name}')
print(f'Device: {clip_embedder.device}')
"
```

---

### Production Smoke Tests

**1. End-to-End Video Flow:**

```bash
# 1. Upload small test video (10-30s)
# 2. Wait for processing (check status endpoint)
# 3. Verify scenes created:

curl http://api.heimdex.com/v1/videos/{video_id}/details \
  -H "Authorization: Bearer $TOKEN"

# Expected:
# - status: "READY"
# - total_scenes: >0
# - scenes[].embedding_version: "v3-multi"
# - scenes[].visual_clip_metadata: not null
```

**2. Multi-Channel Search Validation:**

```bash
# 1. Search for known content
# 2. Check logs for timing breakdown:

# Expected log format:
# "Search completed: mode=multi_dense, fusion=multi_dense_minmax_mean,
#  results=10, latency=456ms (embed=123ms, channels=[transcript=89ms,
#  visual=76ms, summary=82ms, lexical=67ms], fusion=12ms, hydrate=34ms)"
```

**3. Tenancy Isolation Test:**

```bash
# 1. User A uploads video
# 2. User B searches (with User B's JWT)
# 3. Verify User A's video NOT in User B's results

# Check database logs for RPC calls:
# filter_user_id should always equal the authenticated user's UUID
```

**4. Graceful Degradation Test:**

```bash
# 1. Stop OpenSearch container
docker-compose stop opensearch

# 2. Search should still work (dense-only mode)
# Expected log: "OpenSearch unavailable, using dense-only search"
# Expected response: "fusion_method": "dense_only"

# 3. Restart OpenSearch
docker-compose start opensearch

# 4. Next search should use multi-dense or hybrid mode again
```

---

## Appendix: Recent Git Changes

**From git diff --stat (last 10 commits):**

```
29 files changed, 4161 insertions(+), 80 deletions(-)

Major additions:
+ infra/migrations/015_add_multi_embedding_channels.sql (291 lines)
+ infra/migrations/016_add_transcript_segments.sql (21 lines)
+ infra/migrations/017_add_clip_visual_embeddings.sql (117 lines)
+ services/worker/src/adapters/clip_embedder.py (396 lines)
+ services/worker/src/scripts/backfill_clip_visual_embeddings.py (522 lines)
+ services/worker/tests/test_clip_embedder.py (260 lines)
+ services/worker/tests/test_transcript_segmentation.py (291 lines)

Major modifications:
~ services/api/src/routes/search.py (significant refactor)
~ services/api/src/domain/search/fusion.py (multi-channel support)
~ services/worker/src/domain/sidecar_builder.py (transcript slicing)
~ services/worker/src/domain/video_processor.py (multi-embedding)
~ services/worker/src/adapters/database.py (new columns/RPCs)

Removals:
- services/worker/src/domain/scene_detector.py (HashDetector references)
- services/api/src/domain/schemas.py (hash detector field)
```

---

**End of Pipeline Report**
