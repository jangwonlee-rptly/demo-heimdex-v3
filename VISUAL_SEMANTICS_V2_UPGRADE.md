# Visual Semantics v2 Upgrade

This document describes the visual semantics pipeline upgrade for Heimdex, adding richer scene-level analysis with tags and video-level summaries.

## Overview

The upgrade enhances the visual analysis pipeline to provide:
- **Richer scene descriptions**: 1-2 sentences (up to 200 chars) instead of ultra-short descriptions
- **Entity and action extraction**: Structured tags for clickable filtering
- **Video-level summaries**: AI-generated summaries of the entire video
- **Backward compatibility**: Old videos show a reprocess hint

## Database Changes

### Migration: `009_add_rich_semantics.sql`

**video_scenes table:**
- `visual_description` (text): Richer 1-2 sentence description
- `visual_entities` (text[]): Array of main entities (people, objects, locations)
- `visual_actions` (text[]): Array of actions happening in the scene
- `tags` (text[]): Normalized, deduplicated tags from entities + actions
- GIN index on `tags` for efficient filtering

**videos table:**
- `video_summary` (text): AI-generated video summary (3-5 sentences)
- `has_rich_semantics` (boolean): Flag indicating v2 processing

## Worker Service Changes

### 1. OpenAI Client (`services/worker/src/adapters/openai_client.py`)

**Enhanced `analyze_scene_visuals_optimized()`:**
- Updated prompts to request 1-2 sentence descriptions (max 200 chars)
- Prompts now emphasize "who, what, where, mood" for scene-level specificity
- Entities and actions should be concise (max 30 chars each) for use as tags
- Maintains JSON-only output and "no_content" status for uninformative scenes
- Keeps token efficiency with `detail: "low"` and small `max_tokens`

**New `summarize_video_from_scenes()` method:**
- Generates video-level summaries from scene descriptions
- Token-efficient: samples up to 30 scenes (first 10, middle 10, last 10)
- Truncates combined text to ~4000 characters
- Uses `gpt-4o-mini` for cost efficiency
- Returns 3-5 sentence summary in Korean or English
- Handles failures gracefully (logs and returns None)

### 2. Database Adapter (`services/worker/src/adapters/database.py`)

**Updated `create_scene()`:**
- Added parameters: `visual_description`, `visual_entities`, `visual_actions`, `tags`
- Stores arrays as Postgres arrays (empty arrays for no data)

**Updated `update_video_metadata()`:**
- Added parameters: `video_summary`, `has_rich_semantics`
- Only updates non-None values to avoid overwriting existing data

**New `get_scene_descriptions()` method:**
- Retrieves all `visual_description` fields for a video, ordered by index
- Filters out empty/null descriptions
- Used for video summary generation

### 3. Sidecar Builder (`services/worker/src/domain/sidecar_builder.py`)

**Updated `SceneSidecar` dataclass:**
- Added fields: `visual_description`, `visual_entities`, `visual_actions`, `tags`

**New `_normalize_tags()` static method:**
- Combines entities and actions
- Normalizes: trim, lowercase, limit to 30 chars
- Deduplicates while preserving order
- Returns clean list for database storage

**Enhanced `build_sidecar()`:**
- Extracts `visual_description` from OpenAI response
- Extracts `visual_entities` and `visual_actions` arrays
- Calls `_normalize_tags()` to create `tags` array
- Builds `visual_summary` for backward compatibility (combines description + entities + actions)
- Logs counts of extracted entities, actions, and normalized tags

### 4. Video Processor (`services/worker/src/domain/video_processor.py`)

**Updated `_process_single_scene()`:**
- Passes new sidecar fields to `db.create_scene()`

**New Step 8 in `process_video()`:**
- After all scenes processed, fetches scene descriptions
- Calls `openai_client.summarize_video_from_scenes()`
- Saves `video_summary` and sets `has_rich_semantics = True`
- Handles failures gracefully (logs but doesn't fail the job)
- Always marks `has_rich_semantics = True` (even if summary fails, scenes have tags)

## API Service Changes

### 1. Domain Models (`services/api/src/domain/models.py`)

**Updated `Video` class:**
- Added attributes: `video_summary`, `has_rich_semantics`

**Updated `VideoScene` class:**
- Added attributes: `visual_description`, `visual_entities`, `visual_actions`, `tags`

### 2. Schemas (`services/api/src/domain/schemas.py`)

**Updated `VideoResponse`:**
- Added fields: `video_summary`, `has_rich_semantics`

**Updated `VideoSceneResponse`:**
- Added fields: `visual_description`, `visual_entities`, `visual_actions`, `tags`

**Updated `VideoDetailsResponse`:**
- Added field: `reprocess_hint` (optional string)

### 3. Database Adapter (`services/api/src/adapters/database.py`)

**Updated `get_video_scenes()`:**
- Modified SELECT query to include: `visual_description`, `visual_entities`, `visual_actions`, `tags`

### 4. Video Routes (`services/api/src/routes/videos.py`)

**Updated `get_video_details()`:**
- Generates `reprocess_hint` if video is READY but `has_rich_semantics` is False
- Hint: "Reprocess this video to see AI-generated summary and tags."
- Returns new scene fields in response
- Returns `video_summary` and `has_rich_semantics` in video response

**Updated `get_video()` and `list_videos()`:**
- Include `video_summary` and `has_rich_semantics` in VideoResponse objects

## Backward Compatibility

### Old Videos (processed before v2)
- `video_summary`: NULL
- `has_rich_semantics`: NULL or False
- Scene fields (`visual_description`, `visual_entities`, `visual_actions`, `tags`): NULL or empty arrays
- API returns `reprocess_hint` to inform users

### New Videos (processed with v2)
- `has_rich_semantics`: True
- All new fields populated
- No `reprocess_hint` shown

## Token Efficiency

### Scene Analysis
- Single frame per scene (best quality frame)
- Image detail: "low" (85 tokens per image)
- Max tokens: 128 (configurable via `visual_semantics_max_tokens`)
- Temperature: 0.0 (deterministic)
- Model: `gpt-4o-mini` (cheaper than gpt-4o)
- Transcript context: limited to first 200 characters

### Video Summary
- Samples up to 30 scenes (first 10, middle 10, last 10)
- Combined text truncated to 4000 characters
- Max tokens: 300
- Temperature: 0.3
- Model: `gpt-4o-mini`

## Quality & Logging

### Scene Processing
- Logs: status (ok/no_content), description length, entity count, action count, tag count
- Logs: truncated description preview (first 100 chars)
- Logs: sample of normalized tags (first 5)

### Video Summary
- Logs: number of scene descriptions found
- Logs: sampling if >30 scenes
- Logs: truncation if combined text >4000 chars
- Logs: summary preview (first 100 chars)
- Logs: failures without breaking the pipeline

## Configuration

All existing settings are preserved. New behavior is enabled by default:

```python
# services/worker/src/config.py
visual_semantics_enabled: bool = True  # Enable/disable entirely
visual_semantics_model: str = "gpt-4o-mini"  # Model for scene analysis
visual_semantics_max_tokens: int = 128  # Max tokens for scene analysis
visual_semantics_temperature: float = 0.0  # Deterministic output
visual_semantics_include_entities: bool = True  # Extract entities
visual_semantics_include_actions: bool = True  # Extract actions
```

## Testing Recommendations

1. **Run migration:** Apply `009_add_rich_semantics.sql` to database
2. **Test scene processing:** Process a video and verify:
   - `visual_description` is 1-2 sentences
   - `visual_entities` and `visual_actions` are populated
   - `tags` are normalized (lowercase, deduplicated, <30 chars)
3. **Test video summary:** Verify video summary is generated after all scenes processed
4. **Test API responses:** Check that new fields are returned in API responses
5. **Test backward compatibility:** Check that old videos show `reprocess_hint`
6. **Test token efficiency:** Monitor OpenAI usage to ensure costs are reasonable

## Files Modified

### Worker Service
- `/home/ljin/Projects/demo-heimdex-v3/services/worker/src/adapters/openai_client.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/worker/src/adapters/database.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/worker/src/domain/sidecar_builder.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/worker/src/domain/video_processor.py`

### API Service
- `/home/ljin/Projects/demo-heimdex-v3/services/api/src/domain/models.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/api/src/domain/schemas.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/api/src/adapters/database.py`
- `/home/ljin/Projects/demo-heimdex-v3/services/api/src/routes/videos.py`

### Infrastructure
- `/home/ljin/Projects/demo-heimdex-v3/infra/migrations/009_add_rich_semantics.sql`

## Deployment Steps

1. **Apply database migration:**
   ```bash
   # Run 009_add_rich_semantics.sql on your Supabase database
   ```

2. **Deploy worker service:**
   ```bash
   cd services/worker
   # Build and deploy (Railway, Docker, etc.)
   ```

3. **Deploy API service:**
   ```bash
   cd services/api
   # Build and deploy (Railway, Docker, etc.)
   ```

4. **Verify deployment:**
   - Process a test video
   - Check API responses for new fields
   - Monitor logs for proper behavior

## Future Enhancements

Potential improvements for future versions:
- **Tag filtering API:** Add `?tag=...` query parameter to filter scenes by tag
- **Tag popularity:** Aggregate and display most common tags across videos
- **Tag-based search:** Use tags as additional search signals
- **Entity linking:** Link entities to external knowledge bases
- **Action recognition:** Use computer vision for action detection
- **Thumbnail selection:** Use best entities/actions frame for thumbnails
