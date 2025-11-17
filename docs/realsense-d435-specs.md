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
