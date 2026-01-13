# Intel RealSense D435 Technical Specifications

**Source:** Intel RealSense D400 Series Datasheet (Document 337029-005, January 2019)

## Overview

The Intel RealSense D435 is a stereo depth camera with RGB sensor support, designed for robotics, AR/VR, and computer vision applications.

## Supported Resolutions and Frame Rates (USB 3.1 Gen1)

### Depth Stream (Z16 Format - 16 bits)
| Resolution | Frame Rates (FPS) |
|------------|-------------------|
| 1280×720   | 6, 15, 30         |
| 848×480    | 6, 15, 30, 60, 90 |
| 640×480    | 6, 15, 30, 60, 90 |
| 640×360    | 6, 15, 30, 60, 90 |
| 480×270    | 6, 15, 30, 60, 90 |
| 424×240    | 6, 15, 30, 60, 90 |

**Note:** 848×480 is the optimal depth resolution per Intel specifications.

### RGB Color Stream (YUY2 Format - 16 bits)
| Resolution | Frame Rates (FPS) |
|------------|-------------------|
| 1920×1080  | 6, 15, 30         |
| 1280×720   | 6, 15, 30         |
| 960×540    | 6, 15, 30, 60     |
| 848×480    | 6, 15, 30, 60     |
| 640×480    | 6, 15, 30, 60     |
| 640×360    | 6, 15, 30, 60     |
| 424×240    | 6, 15, 30, 60     |
| 320×240    | 6, 30, 60         |
| 320×180    | 6, 30, 60         |

### Infrared Streams (Y8 Format - 8 bits, Left & Right Imagers)
| Resolution | Frame Rates (FPS) |
|------------|-------------------|
| 1280×720   | 6, 15, 30         |
| 848×480    | 6, 15, 30, 60, 90 |
| 640×480    | 6, 15, 30, 60, 90 |
| 640×360    | 6, 15, 30, 60, 90 |
| 480×270    | 6, 15, 30, 60, 90 |
| 424×240    | 6, 15, 30, 60, 90 |

## Current Configuration

**Our Setup:**
- RGB: 1280×720 @ 30 FPS
- Depth: 1280×720 @ 30 FPS
- Interface: USB 3.0 Type-C

## Field of View

### Depth Camera FOV
- **Horizontal × Vertical × Diagonal:** 85.2° × 58° × ~90°

### RGB Camera FOV  
- **Horizontal × Vertical × Diagonal:** 69.4° × 42.5° × 77° (±3°)

## Depth Specifications

- **Technology:** Active Stereoscopic (stereo vision with IR projector)
- **Operating Range:** ~0.3m to 3m (0.3m minimum, extends up to 10m)
- **Depth Format:** Z16 (16-bit depth values in millimeters)
- **Baseline:** 50mm between stereo cameras

## Physical Specifications

- **Dimensions:** 90mm × 25mm × 25mm
- **Interface:** USB 3.0 Type-C
- **Power:** USB bus-powered

## Visual Presets

The D435's depth calculations use over 40 internal parameters. Intel provides presets that bundle these for common use cases.

### Available Presets

| Preset | Fill Factor | Accuracy | Use Case |
|--------|-------------|----------|----------|
| **Default** (1) | Medium | Medium | General use, clean edges, reduced point cloud spraying |
| **Hand** (2) | Varies | Varies | Close-range hand tracking, gesture recognition |
| **High Accuracy** (3) | Low | Highest | Collision avoidance, autonomous robots, object scanning |
| **High Density** (4) | Highest | Lower | Photography, background segmentation, seeing more objects |
| **Medium Density** (5) | Medium | Medium | General robotics, object manipulation, balanced scenarios |

### Key Trade-off: Fill Factor vs Accuracy

- **Fill factor** = percentage of pixels with valid depth values (fewer holes)
- **Accuracy** = confidence threshold for accepting depth measurements

**High Density**: Accepts more depth measurements including lower-confidence ones. Fuller depth image with fewer holes, but some values may be incorrect ("hallucinations").

**High Accuracy**: Only accepts high-confidence measurements. Sparser depth image with more holes, but values are more reliable. Critical for robots where false depth could cause collisions.

**Medium Density**: Balances both. Good accuracy while maintaining reasonable coverage.

### Setting Presets in Python

```python
import pyrealsense2 as rs

pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)

pipeline.start(config)
device = pipeline.get_active_profile().get_device()
depth_sensor = device.first_depth_sensor()

# Preset values: 0=Custom, 1=Default, 2=Hand, 3=HighAccuracy, 4=HighDensity, 5=MediumDensity
depth_sensor.set_option(rs.option.visual_preset, 5)  # Medium Density
```

### Recommended Preset for Grasp Planning

For assistive robotics grasp planning at 0.3-0.8m range:
- **Medium Density** (5): Good balance for detecting grasp surfaces while maintaining accuracy
- **High Accuracy** (3): Consider if false depth readings cause grasp failures; post-processing filters can fill gaps

Test both presets with your specific objects to determine which works better.

## Depth Processing Features

- Spatial filtering with hole filling
- Alignment between depth and color streams
- Configurable depth quality settings

## Available Configuration Options

### RGB Sensor Options (rs.option)
- `enable_auto_exposure` - Enable/disable auto-exposure (0/1)
- `exposure` - Manual exposure value (range: 1-10000, typical < 2500 for low noise)
- `enable_auto_white_balance` - Enable/disable auto white balance (0/1)
- `white_balance` - Manual white balance (range: 2800-6500, default: 4600)
- `brightness` - Post-processing brightness adjustment
- `contrast` - Edge contrast adjustment
- `saturation` - Color intensity
- `sharpness` - Edge sharpening
- `gamma` - Tone curve adjustment
- `gain` - Sensor ISO/gain
- `hue` - Color hue shift
- `backlight_compensation` - Backlight compensation
- `power_line_frequency` - Anti-flicker (1=50Hz, 2=60Hz)

### Depth Processing Options
- `holes_fill` - Spatial filter hole filling level (0-5)
- Various depth quality and accuracy controls

## Recommended Configurations

### For Segmentation Accuracy (Our Use Case)
- **Priority:** Clean edges over brightness
- **RGB Resolution:** 1920×1080 @ 30 FPS (higher detail for segmentation)
- **Depth Resolution:** 1280×720 @ 30 FPS OR 848×480 @ 30 FPS (Intel optimal)
- **Auto-Exposure:** Enabled (camera handles lighting automatically)
- **Auto White Balance:** Enabled
- **Power Line Frequency:** 60Hz (North America, reduces flicker)

### Alternative: Higher Frame Rate Depth
- **RGB:** 1280×720 @ 30 FPS
- **Depth:** 848×480 @ 90 FPS (smoother depth tracking, Intel recommended optimal)

## Notes

- Depth and color streams operate independently (separate USB endpoints)
- Higher exposure (>2500) introduces sensor noise that can degrade segmentation quality
- Neural network segmentation models prioritize clean edges over brightness
- For stationary objects (home assistant use case), frame rate is less critical than resolution
