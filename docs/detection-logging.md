# Detection Logging and Stability Analysis

This document explains how to use the detection logging system to measure and analyze tracking stability.

## Overview

The detection logging system records frame-by-frame object detection data, allowing you to:
- Measure flickering (objects appearing/disappearing rapidly)
- Analyze object lifetime (how long objects persist)
- Compare raw detections vs tracked output
- Quantify position stability
- Evaluate tracking improvements

## Quick Start

### 1. Enable Logging During Session

**Keyboard Shortcut:** Press `L` to toggle detection logging on/off

When enabled, you'll see:
```
✓ Detection logging enabled: logs/detections/detections_20250116_143022.jsonl
```

When disabled:
```
✓ Detection log saved: logs/detections/detections_20250116_143022.jsonl (1247 frames)
```

### 2. Analyze the Log

```bash
# Analyze specific log file
python scripts/analyze_detections.py logs/detections/detections_20250116_143022.jsonl

# Or analyze latest log in directory
python scripts/analyze_detections.py logs/detections/
```

## Analysis Metrics

The analysis script provides comprehensive stability metrics:

### Session Summary
- Total frames captured
- Session duration
- Average FPS

### Object Lifetimes
- Total unique objects detected
- Average/median/min/max lifetime (in frames)
- Distribution: short-lived (<5 frames), medium (5-29), long (30+)

**Example output:**
```
Total unique objects:  18
Average lifetime:      42.3 frames
Median lifetime:       35.0 frames
Min lifetime:          2 frames
Max lifetime:          156 frames

Lifetime distribution:
  < 5 frames:          3 (16.7%)
  5-29 frames:         7 (38.9%)
  >= 30 frames:        8 (44.4%)
```

### Flickering Analysis
- Total object "runs" (consecutive appearances)
- Flickering runs (<5 frames) vs stable runs (≥5 frames)
- Objects that reappeared after disappearing

**Lower flickering % = better stability**

**Example output:**
```
Total object runs:     23
Flickering runs (<5f): 5 (21.7%)
Stable runs (>=5f):    18 (78.3%)

Objects that flickered (reappeared):
  4 / 18 (22.2%)
```

### Position Stability
- Position variance for objects tracked >10 frames
- Measured in pixels (RMS of x and y variance)

**Lower variance = smoother tracking**

**Example output:**
```
Objects tracked >10 frames: 12
Average position variance:  8.4px
Median position variance:   6.2px
```

### Detection vs Tracking
- Average objects per frame (raw vs tracked)
- Reduction from filtering
- Frame-to-frame variance improvement

**Example output:**
```
Average raw detections:     4.8 objects/frame
Average tracked detections: 3.2 objects/frame
Reduction:                  1.6 (33.3%)

Frame-to-frame variance:
  Raw:                      2.45
  Tracked:                  1.12
  Improvement:              54.3%
```

## Workflow for Testing Tracking Improvements

### Before Making Changes

1. Enable logging: Press `L`
2. Run test scenario (e.g., 30 seconds of object detection)
3. Disable logging: Press `L`
4. Analyze: `python scripts/analyze_detections.py logs/detections/`
5. **Note the baseline metrics** (flickering %, variance, etc.)

### After Making Changes

1. Repeat steps 1-4 with same test scenario
2. Compare metrics to baseline
3. Look for improvements in:
   - **Flickering runs**: Should decrease
   - **Position variance**: Should decrease
   - **Frame-to-frame variance**: Should decrease
   - **Average lifetime**: Should increase

## Log File Format

Logs are stored in **JSONL format** (JSON Lines) - one JSON object per line.

**Location:** `logs/detections/detections_YYYYMMDD_HHMMSS.jsonl`

### Structure

**Session start:**
```json
{"type": "session_start", "timestamp": "20250116_143022", "start_time": 1705416622.5}
```

**Frame data:**
```json
{
  "type": "frame",
  "frame": 42,
  "timestamp": 1.234,
  "raw_count": 5,
  "tracked_count": 3,
  "raw_detections": [
    {"class": "cup", "center": [450, 320], "box": [420, 290, 480, 350]},
    ...
  ],
  "tracked_detections": [
    {"id": 0, "class": "cup", "center": [452, 318], "box": [422, 288, 482, 348]},
    ...
  ]
}
```

**Session end:**
```json
{"type": "session_end", "timestamp": 45.678, "total_frames": 1247}
```

## Performance Impact

- **Minimal CPU impact**: Logging is asynchronous
- **Disk usage**: ~1-2 KB per frame (~1 MB per 1000 frames)
- **Recommended**: Disable when not actively analyzing

## Tips

1. **Short test sessions**: 30-60 seconds is usually sufficient for analysis
2. **Consistent scenarios**: Use same scene/objects when comparing before/after
3. **Focus on key metrics**:
   - Flickering % (lower is better)
   - Position variance (lower is better)
   - Average lifetime (higher is better)
4. **Export results**: Copy console output to compare metrics over time

## Interpreting Results

### Good Tracking Stability
- Flickering runs: <20%
- Position variance: <10px
- Average lifetime: >30 frames
- Frame variance reduction: >40%

### Poor Tracking Stability
- Flickering runs: >40%
- Position variance: >25px
- Average lifetime: <15 frames
- Frame variance reduction: <20%

## Troubleshooting

### Log directory not created
The `logs/detections/` directory is created automatically when logging is enabled.

### Analysis script fails
Ensure you're running from the project root:
```bash
cd /path/to/access-ability-arm
source venv/bin/activate
python scripts/analyze_detections.py logs/detections/
```

### Empty log file
Make sure object detection mode is active when logging. Logging only works in "objects" or "combined" modes.

## Example Comparison

**Before Kalman Filter:**
```
Flickering runs: 45 (38.1%)
Position variance: 18.3px
Average lifetime: 22.4 frames
```

**After Kalman Filter:**
```
Flickering runs: 12 (12.8%)
Position variance: 6.7px
Average lifetime: 51.2 frames
```

**Result:** 66% reduction in flickering, 63% improvement in position stability!
