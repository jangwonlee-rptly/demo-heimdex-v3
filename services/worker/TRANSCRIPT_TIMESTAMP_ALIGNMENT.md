# Timestamp-Aligned Transcript Slicing

## Overview

This document describes the timestamp-aligned transcript slicing implementation that improves the accuracy of scene-to-transcript mapping in Heimdex video processing.

## Problem Statement

The original implementation used proportional character-based slicing to extract transcript segments for each scene:

```python
# Old approach (proportional)
start_char = (scene.start_s / total_duration_s) * total_chars
end_char = (scene.end_s / total_duration_s) * total_chars
segment = full_transcript[start_char:end_char]
```

**Issues with this approach:**
- Assumes uniform speech rate across the entire video
- Breaks whenever speech rate changes (silence, music, variable pacing)
- Scenes receive incorrect transcript text when speech is not evenly distributed
- Degrades transcript embedding quality and search accuracy

## Solution

Use Whisper's `verbose_json` response format to obtain segment-level timestamps, then map scenes to transcript segments using actual time windows instead of character proportions.

## Implementation

### 1. WhisperSegment Data Model

```python
@dataclass
class WhisperSegment:
    start: float              # Segment start time in seconds
    end: float                # Segment end time in seconds
    text: str                 # Transcribed text for this segment
    no_speech_prob: Optional[float]   # Speech quality indicator
    avg_logprob: Optional[float]      # Confidence score
```

### 2. Segment Storage

**Database:**
- Added `transcript_segments JSONB` column to `videos` table (migration 016)
- Stores array of segment objects with timestamps

**Caching:**
- Segments are cached alongside full transcript text
- Enables idempotent video processing (no re-transcription on retry)

### 3. Timestamp-Aligned Extraction

```python
def _extract_transcript_segment_from_segments(
    segments: list,
    scene_start_s: float,
    scene_end_s: float,
    video_duration_s: float,
    context_pad_s: float = 3.0,
    min_chars: int = 200,
) -> str:
    """
    Extract transcript using Whisper's timestamp-aligned segments.

    Algorithm:
    1. Find all segments that overlap with [scene_start_s, scene_end_s]
    2. Concatenate their text in chronological order
    3. If result < min_chars, expand time window by ±context_pad_s
    4. Normalize whitespace and return
    """
```

**Overlap Detection:**
- Uses strict inequalities: `seg_end > start AND seg_start < end`
- Excludes segments that only touch at boundaries (no actual overlap)

**Context Expansion:**
- If extracted text is too short (< `min_chars`), expands the time window
- Expansion is time-based (±`context_pad_s` seconds), not character-based
- Clamps to `[0, video_duration_s]` to stay within video bounds

### 4. Backward Compatibility

**Fallback Behavior:**
- If `transcript_segments` is `None` (older cached transcripts), falls back to proportional slicing
- Full transcript text is always preserved
- Existing API consumers are unaffected

**Logging:**
```
"Using timestamp-aligned transcript extraction for scene X"
"Falling back to proportional transcript extraction for scene X"
```

## Benefits

1. **Accuracy:** Scenes get the transcript that was actually spoken during that time window
2. **Search Quality:** Transcript embeddings better represent actual scene content
3. **Language Support:** Works identically for Korean, English, Japanese, etc.
4. **Robustness:** Handles variable speech rate, silence, music, and pauses correctly
5. **Idempotency:** Cached segments prevent redundant Whisper API calls

## Testing

Comprehensive unit tests cover:
- Exact time overlap
- Partial overlap (scene starts/ends mid-segment)
- No overlap (empty result)
- Context expansion when text is too short
- Boundary clamping (0 and video_duration_s)
- Empty segments list
- Out-of-order segments (sorted internally)
- Whitespace normalization
- Korean, CJK, and mixed-language text

Run tests in Docker:
```bash
docker compose -f docker-compose.test.yml run --rm worker-test pytest tests/test_transcript_segmentation.py -v
```

## Migration Path

**For New Videos:**
- Automatically uses timestamp-aligned extraction
- Whisper segments are captured and stored in DB

**For Existing Videos:**
- No immediate action required
- Videos processed before this change will use fallback (proportional slicing)
- To upgrade: trigger video reprocessing (will re-call Whisper with `verbose_json`)

## Future Improvements

1. **Upgrade to Whisper v3:** Consider using latest Whisper model when stable (may improve segment boundaries)
2. **Word-Level Timestamps:** Explore even finer-grained alignment if needed
3. **Segment Metadata:** Store and utilize `no_speech_prob` for further quality filtering
4. **Performance:** Investigate caching segment lookups if extraction becomes a bottleneck

## References

- Implementation: `services/worker/src/domain/sidecar_builder.py:993-1051`
- Database migration: `infra/migrations/016_add_transcript_segments.sql`
- Tests: `services/worker/tests/test_transcript_segmentation.py`
- Whisper segments model: `services/worker/src/adapters/openai_client.py:17-35`
