# Scene Detection Configuration

## Overview

Heimdex uses PySceneDetect for intelligent scene detection in videos. As of this update, the scene detection pipeline supports multiple detection strategies with **AdaptiveDetector as the default**.

## Supported Detection Strategies

### 1. AdaptiveDetector (Default)
**Best for**: Videos with varying content, different lighting conditions, and gradual transitions.

AdaptiveDetector uses a rolling window approach to dynamically adjust detection thresholds based on local content changes. This makes it more robust than traditional content-based detection, especially for:
- Videos with varying brightness/contrast
- Scenes with gradual transitions
- Content with different visual characteristics

**Configuration:**
```bash
HEIMDEX_SCENE_DETECTOR=adaptive
HEIMDEX_SCENE_ADAPTIVE_THRESHOLD=3.0          # Sensitivity (lower = more scenes)
HEIMDEX_SCENE_ADAPTIVE_WINDOW_WIDTH=2         # Rolling window size
HEIMDEX_SCENE_ADAPTIVE_MIN_CONTENT_VAL=15.0   # Minimum content change to detect
HEIMDEX_SCENE_MIN_LEN_SECONDS=1.0             # Minimum scene duration
```

### 2. ContentDetector
**Best for**: Videos with distinct, sharp scene cuts.

ContentDetector uses a fixed threshold to detect scene changes based on frame-to-frame differences. This is the traditional approach and works well for:
- Videos with clear scene cuts
- Content with consistent lighting
- Simple cut-based editing

**Configuration:**
```bash
HEIMDEX_SCENE_DETECTOR=content
HEIMDEX_SCENE_CONTENT_THRESHOLD=27.0    # Detection threshold (PySceneDetect default)
HEIMDEX_SCENE_MIN_LEN_SECONDS=1.0       # Minimum scene duration
```

## Configuration Reference

All scene detection settings can be configured via environment variables:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEIMDEX_SCENE_DETECTOR` | string | `"adaptive"` | Detection strategy: `"adaptive"` or `"content"` |
| `HEIMDEX_SCENE_MIN_LEN_SECONDS` | float | `1.0` | Minimum scene length in seconds |
| **AdaptiveDetector Settings** | | | |
| `HEIMDEX_SCENE_ADAPTIVE_THRESHOLD` | float | `3.0` | Adaptive threshold for scene changes (lower = more sensitive) |
| `HEIMDEX_SCENE_ADAPTIVE_WINDOW_WIDTH` | int | `2` | Rolling window width for adaptive detection |
| `HEIMDEX_SCENE_ADAPTIVE_MIN_CONTENT_VAL` | float | `15.0` | Minimum content value to trigger detection |
| **ContentDetector Settings** | | | |
| `HEIMDEX_SCENE_CONTENT_THRESHOLD` | float | `27.0` | Content threshold (PySceneDetect default) |

## Tuning Guidelines

### AdaptiveDetector Tuning

**Too many scenes detected?**
- Increase `HEIMDEX_SCENE_ADAPTIVE_THRESHOLD` (e.g., from 3.0 to 5.0)
- Increase `HEIMDEX_SCENE_ADAPTIVE_MIN_CONTENT_VAL` (e.g., from 15.0 to 20.0)
- Increase `HEIMDEX_SCENE_MIN_LEN_SECONDS` (e.g., from 1.0 to 2.0)

**Too few scenes detected?**
- Decrease `HEIMDEX_SCENE_ADAPTIVE_THRESHOLD` (e.g., from 3.0 to 2.0)
- Decrease `HEIMDEX_SCENE_ADAPTIVE_MIN_CONTENT_VAL` (e.g., from 15.0 to 10.0)

**Scene boundaries are imprecise?**
- Adjust `HEIMDEX_SCENE_ADAPTIVE_WINDOW_WIDTH`:
  - Larger values (3-4) = smoother but less precise
  - Smaller values (1-2) = more responsive but potentially noisy

### ContentDetector Tuning

**Too many scenes detected?**
- Increase `HEIMDEX_SCENE_CONTENT_THRESHOLD` (e.g., from 27.0 to 35.0)
- Increase `HEIMDEX_SCENE_MIN_LEN_SECONDS`

**Too few scenes detected?**
- Decrease `HEIMDEX_SCENE_CONTENT_THRESHOLD` (e.g., from 27.0 to 20.0)

## Migration from ContentDetector

If you were previously using the hardcoded ContentDetector, the system now defaults to **AdaptiveDetector** which generally provides better results.

**To keep using ContentDetector** (maintain old behavior):
```bash
export HEIMDEX_SCENE_DETECTOR=content
export HEIMDEX_SCENE_CONTENT_THRESHOLD=27.0
```

**To switch to AdaptiveDetector** (recommended):
```bash
export HEIMDEX_SCENE_DETECTOR=adaptive
export HEIMDEX_SCENE_ADAPTIVE_THRESHOLD=3.0
```

Or simply omit these variables to use the defaults (AdaptiveDetector).

## Architecture

### Detection Flow

```
1. Video file → FFprobe (extract metadata: duration, FPS)
2. Create detector via factory:
   - get_scene_detector(fps) → AdaptiveDetector or ContentDetector
3. PySceneDetect runs detection with configured detector
4. Convert detected scenes to Scene objects (index, start_s, end_s)
5. Pass scenes to downstream pipeline (ASR, visual semantics, etc.)
```

### Code Structure

**Factory Pattern** (`src/domain/scene_detector.py`):
```python
def get_scene_detector(fps: float = 30.0) -> PySceneDetector:
    """Creates detector based on settings.scene_detector"""
    if settings.scene_detector == "adaptive":
        return AdaptiveDetector(...)
    elif settings.scene_detector == "content":
        return ContentDetector(...)
```

**Entry Point** (`SceneDetector.detect_scenes()`):
```python
detector = get_scene_detector(fps=metadata.frame_rate)
scene_list = detect(video_path, detector)
```

### Key Files

| File | Changes |
|------|---------|
| `src/config.py` | Added scene detection configuration settings |
| `src/domain/scene_detector.py` | Added `SceneDetectionStrategy` enum, `get_scene_detector()` factory, refactored `detect_scenes()` |
| `src/domain/video_processor.py` | Updated to pass FPS to `detect_scenes()` |

## Logging

The scene detection pipeline logs the following at INFO level:

```
INFO: Detecting scenes in /path/to/video.mp4 using 'adaptive' detector
INFO: Creating AdaptiveDetector with threshold=3.0, window_width=2, min_content_val=15.0, min_scene_len=30 frames (1.0s)
INFO: Detected 15 scenes using adaptive detector
```

For unknown detector strategies:
```
WARNING: Unknown scene detector strategy 'unknown', falling back to AdaptiveDetector
```

## Performance Considerations

- **AdaptiveDetector**: Slightly slower than ContentDetector due to rolling window calculations, but the difference is negligible for most videos
- **Min scene length**: Setting this too low can result in many micro-scenes, increasing processing time for downstream tasks (ASR, visual semantics, embeddings)
- **Recommended**: Keep `scene_min_len_seconds >= 1.0` to avoid over-segmentation

## Future Extensibility

The factory pattern makes it easy to add new detection strategies in the future:

```python
class SceneDetectionStrategy(str, Enum):
    ADAPTIVE = "adaptive"
    CONTENT = "content"
    THRESHOLD = "threshold"     # Future: ThresholdDetector
    HISTOGRAM = "histogram"     # Future: HistogramDetector
    HASH = "hash"              # Future: HashDetector
```

Simply extend the enum and add a new case in `get_scene_detector()`.

## Troubleshooting

**Problem**: "Unknown scene detector strategy" warning
- **Solution**: Check that `HEIMDEX_SCENE_DETECTOR` is set to either `"adaptive"` or `"content"`

**Problem**: No scenes detected (single scene covering entire video)
- **Solution**: Try lowering the threshold:
  - For AdaptiveDetector: Decrease `HEIMDEX_SCENE_ADAPTIVE_THRESHOLD`
  - For ContentDetector: Decrease `HEIMDEX_SCENE_CONTENT_THRESHOLD`

**Problem**: Too many tiny scenes
- **Solution**: Increase `HEIMDEX_SCENE_MIN_LEN_SECONDS` (e.g., to 2.0 or 3.0)

**Problem**: Scenes don't align with visual transitions
- **Solution**: Try switching detectors:
  - If using ContentDetector → Try AdaptiveDetector (better for gradual transitions)
  - If using AdaptiveDetector → Try ContentDetector (better for sharp cuts)
