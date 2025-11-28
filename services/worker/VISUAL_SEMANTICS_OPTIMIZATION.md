# Visual Semantics Pipeline Optimization

## Overview

This document describes the optimizations made to the visual semantics pipeline to reduce token usage and eliminate useless OpenAI API calls for low-information scenes.

## Problem Statement

Previously, the system would:
1. Extract multiple keyframes for every scene
2. Call OpenAI vision API for every scene regardless of visual quality
3. Receive long apologetic Korean responses like "죄송합니다. 이 이미지를 기반으로..." for uninformative scenes
4. Waste tokens on scenes that are completely black, too blurry, or contain no recognizable content

## Solution Architecture

### 1. Frame Quality Pre-filtering (`src/domain/frame_quality.py`)

**Purpose**: Determine if frames are worth sending to OpenAI before making expensive API calls.

**Components**:
- `FrameQualityChecker.check_frame(frame_path)`: Evaluates a single frame
  - **Brightness check**: Calculates mean intensity (0-255 scale)
  - **Blur check**: Uses Laplacian variance to detect sharpness
  - Returns `FrameQualityResult` with assessment details

- `FrameQualityChecker.find_best_frame(frame_paths)`: Selects the best frame from candidates
  - Scores frames based on brightness (prefers mid-range) and sharpness
  - Returns `None` if all frames are uninformative
  - **Result**: Only send best frame to OpenAI (not all keyframes)

**Configuration** (see `src/config.py`):
- `visual_brightness_threshold`: Minimum brightness (default: 15.0)
- `visual_blur_threshold`: Minimum Laplacian variance (default: 50.0, lowered from 100.0 to reduce false negatives)
- `visual_semantics_retry_on_no_content`: Retry with next best frame if first returns no_content (default: True)
- `visual_semantics_max_frame_retries`: Max frames to try before giving up (default: 2)

### 2. Strict JSON Schema Prompt (`src/adapters/openai_client.py`)

**New Method**: `analyze_scene_visuals_optimized()`

**Key Features**:
- **Forced JSON response**: Uses `response_format={"type": "json_object"}`
- **No apologies**: System prompt explicitly forbids "죄송합니다" style responses
- **Structured output**:
  ```json
  {
    "status": "ok" | "no_content",
    "description": "짧은 한국어 설명 (30자 이내)",
    "main_entities": ["명사구"],
    "actions": ["동사구"],
    "confidence": 0.0-1.0
  }
  ```
- **Token-efficient**:
  - Single frame (not multiple keyframes)
  - Short system prompt
  - Truncated transcript context (max 200 chars)
  - Low detail image encoding
  - `max_tokens=128` (vs previous 150)
  - `temperature=0.0` (deterministic, no rambling)

**Configuration**:
- `visual_semantics_model`: Model to use (default: "gpt-4o-mini" - upgraded from gpt-5-nano for better accuracy)
- `visual_semantics_max_tokens`: Response token limit (default: 150 - increased for richer descriptions)
- `visual_semantics_temperature`: Temperature setting (default: 0.0)
- `visual_semantics_include_entities`: Toggle entities in response (default: True)
- `visual_semantics_include_actions`: Toggle actions in response (default: True)

**Prompt Improvements**:
- More aggressive extraction: Forces OpenAI to describe ANY visible content
- Only allows "no_content" for completely black or completely blurred frames
- Emphasizes extraction of ALL visible elements (people, objects, text, colors, backgrounds)
- Encourages analysis even when uncertain (using lower confidence scores)

### 3. Transcript-First Strategy (`src/domain/sidecar_builder.py`)

**Refactored**: `build_sidecar()` method

**Decision Flow**:
```
1. Extract transcript segment for scene
2. Check if transcript is meaningful (>20 chars)
3. Extract keyframes
4. Find best quality frame using pre-filtering
   ├─ If no informative frames found:
   │  ├─ Skip OpenAI call entirely (SAVE TOKENS)
   │  └─ Log: "skipping OpenAI call (saved tokens)"
   │
   └─ If informative frame found:
      ├─ Call optimized OpenAI method
      └─ Process JSON response:
         ├─ status="no_content": Skip visual semantics
         └─ status="ok": Build visual summary from JSON fields
5. Build combined_text (transcript + visual summary)
6. Generate embedding
```

**Key Optimization**:
- Scenes with only transcript (no good frames): **No OpenAI vision call**
- Scenes with meaningful content but bad visuals: **Transcript-only embedding**
- Completely empty scenes: Embed placeholder text ("내용 없음")

### 4. Configuration Settings (`src/config.py`)

New environment variables (all prefixed with `HEIMDEX_` in .env):

**Visual Quality Thresholds**:
- `visual_brightness_threshold`: Min brightness (0-255) for informative frames
- `visual_blur_threshold`: Min blur score (Laplacian variance) for sharp frames

**Visual Semantics Control**:
- `visual_semantics_enabled`: Master toggle (set to `False` to disable all visual analysis)
- `visual_semantics_model`: OpenAI model name
- `visual_semantics_max_tokens`: Response token limit
- `visual_semantics_temperature`: Temperature (0 = deterministic)
- `visual_semantics_include_entities`: Include main_entities in JSON
- `visual_semantics_include_actions`: Include actions in JSON

## When OpenAI is Called

| Condition | OpenAI Called? | Reason |
|-----------|----------------|--------|
| All frames too dark/blurry | ❌ No | Pre-filtered by frame quality checker |
| Good frame + meaningful transcript | ✅ Yes (1-2 frames) | Full visual + transcript context with multi-frame fallback |
| Good frame + no transcript | ✅ Yes (1-2 frames) | Visual-only analysis with multi-frame fallback |
| No good frames + meaningful transcript | ❌ No | Transcript-only embedding (no visual needed) |
| No good frames + no transcript | ❌ No | Placeholder embedding ("내용 없음") |
| `visual_semantics_enabled=False` | ❌ No | Disabled globally |

## Multi-Frame Fallback Strategy

**New Feature**: If the first frame returns `status="no_content"`, the system will automatically try the next best quality frame.

**How it works**:
1. Extract and rank all keyframes by quality score (brightness + sharpness)
2. Try the best frame first
3. If result is "no_content" AND retry is enabled, try the next best frame
4. Continue until max_frame_retries is reached or "ok" status is received
5. This significantly improves accuracy for scenes where one frame might be a transition or poor moment

**Configuration**:
- `visual_semantics_retry_on_no_content`: Enable/disable retry (default: True)
- `visual_semantics_max_frame_retries`: Maximum frames to try (default: 2)

**Cost Impact**: Minimal - only retries when first frame fails, and stops immediately on success

## Expected Token Savings

### Per Scene Savings:
1. **Eliminated calls** (black/blurry scenes): ~100-200 tokens saved per skipped call
2. **Reduced keyframes**: 3 frames → 1 frame = ~66% reduction in image tokens
3. **Shorter responses**: JSON schema with 30-char limit vs free-form 150 tokens
4. **No apologies**: Eliminate 50-100 token apologetic responses

### Estimated Overall Savings:
- **Conservative estimate**: 40-60% reduction in vision API costs
- **Best case** (many low-quality scenes): 70-80% reduction

## Logging and Observability

Key log messages to monitor:

```
INFO: "Found informative frame for scene X, calling OpenAI for visual analysis"
INFO: "No informative frames found for scene X, skipping OpenAI call (saved tokens)"
INFO: "Visual analysis returned no_content for scene X, skipping visual semantics"
INFO: "Best frame selected: scene_X_frame_Y.jpg (score=0.85)"
```

## Backward Compatibility

- **Old method preserved**: `analyze_scene_visuals()` still exists for backward compatibility
- **Gradual migration**: New method is `analyze_scene_visuals_optimized()`
- **Configuration**: All optimizations can be disabled via settings

## Testing and Tuning

### Recommended Tuning Process:
1. Start with default thresholds (brightness: 15.0, blur: 50.0)
2. Monitor logs for skipped scenes
3. Spot-check a few "skipped" scenes to verify they're truly uninformative
4. Adjust thresholds if needed:
   - Increase `visual_brightness_threshold` to skip more dark scenes
   - Increase `visual_blur_threshold` to skip more blurry scenes
   - Decrease `visual_blur_threshold` if too many meaningful frames are being rejected (current default: 50.0)

### Test Cases:
- ✅ Completely black frames (e.g., scene transitions)
- ✅ Very blurry/out-of-focus frames
- ✅ Scenes with meaningful visuals
- ✅ Scenes with transcript only
- ✅ Empty scenes (no transcript, no good visuals)

## Implementation Files

| File | Purpose |
|------|---------|
| `src/domain/frame_quality.py` | Frame quality checks (NEW) |
| `src/adapters/openai_client.py` | Optimized OpenAI method (MODIFIED) |
| `src/domain/sidecar_builder.py` | Transcript-first logic (MODIFIED) |
| `src/domain/video_processor.py` | Pass video duration (MODIFIED) |
| `src/config.py` | Configuration settings (MODIFIED) |

## Future Enhancements

Potential further optimizations:
1. **Adaptive quality thresholds**: Learn optimal thresholds per video type
2. **Token usage tracking**: Add detailed token accounting and reporting
3. **Scene type classification**: Different strategies for different scene types
4. **Batch API calls**: If OpenAI supports batch vision API in future
