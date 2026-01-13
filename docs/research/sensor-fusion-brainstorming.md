# Sensor Fusion Brainstorming

Notes and ideas for fusing multiple depth sensors (RealSense D435 + iPad LiDAR or other sensors) to improve depth accuracy and coverage for grasp planning.

## Current Sensor: RealSense D435

### Strengths
- Good resolution (848×480 depth)
- Works well at 0.3-3m range
- RGB-D aligned streams
- Active IR projection helps with textureless surfaces

### Limitations
- No native per-pixel confidence stream (stereo cameras don't provide this)
- Struggles with transparent/reflective surfaces
- Depth holes on textureless regions
- Accuracy degrades with distance (~2% error at 2m)

## D435 Confidence Estimation (DIY Approaches)

Since the D435 doesn't provide native confidence values, here are methods to estimate per-pixel reliability:

### 1. Binary Validity Mask
The simplest approach - treat zero values as "no confidence":

```python
import numpy as np

def get_validity_mask(depth_image):
    """Binary mask: 1 = valid depth, 0 = no depth"""
    return (depth_image > 0).astype(np.float32)
```

### 2. Temporal Consistency
Track depth variance over multiple frames - stable values indicate higher confidence:

```python
import numpy as np
from collections import deque

class TemporalConfidenceEstimator:
    def __init__(self, history_size=5):
        self.depth_history = deque(maxlen=history_size)
    
    def update(self, depth_image):
        """Add frame and compute confidence based on temporal stability"""
        self.depth_history.append(depth_image.astype(np.float32))
        
        if len(self.depth_history) < 2:
            # Not enough history, return validity mask
            return (depth_image > 0).astype(np.float32)
        
        # Stack frames and compute variance
        depth_stack = np.array(self.depth_history)
        
        # Mask out zeros before computing variance
        valid_mask = depth_stack > 0
        depth_stack_masked = np.where(valid_mask, depth_stack, np.nan)
        
        # Variance across time (ignoring NaN)
        with np.errstate(all='ignore'):
            variance = np.nanvar(depth_stack_masked, axis=0)
        
        # Convert variance to confidence (low variance = high confidence)
        # Typical depth noise is ~2-10mm, so variance of 100mm² is significant
        confidence = 1.0 / (1.0 + variance / 100.0)
        
        # Zero out where current frame has no depth
        confidence = np.where(depth_image > 0, confidence, 0)
        
        return confidence.astype(np.float32)
```

### 3. Edge-Based Confidence
Depth at RGB edges (occlusion boundaries) is often unreliable:

```python
import cv2
import numpy as np

def get_edge_confidence(rgb_image, depth_image, edge_penalty=0.5):
    """Lower confidence near RGB edges (potential occlusion boundaries)"""
    # Detect edges in RGB
    gray = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # Dilate edges to create uncertainty zone
    kernel = np.ones((5, 5), np.uint8)
    edge_zone = cv2.dilate(edges, kernel, iterations=2)
    
    # Create confidence map
    confidence = np.ones_like(depth_image, dtype=np.float32)
    confidence[edge_zone > 0] = edge_penalty
    confidence[depth_image == 0] = 0  # No depth = no confidence
    
    return confidence
```

### 4. Distance-Based Confidence
D435 accuracy degrades with distance:

```python
import numpy as np

def get_distance_confidence(depth_image, depth_scale=0.001, 
                            optimal_range=(0.3, 1.0), max_range=3.0):
    """
    Confidence based on distance from camera.
    
    D435 specs:
    - Optimal: 0.3-1.0m (highest accuracy)
    - Good: 1.0-2.0m 
    - Degraded: 2.0-3.0m
    - Unreliable: >3.0m
    """
    # Convert to meters
    depth_m = depth_image.astype(np.float32) * depth_scale
    
    confidence = np.ones_like(depth_m)
    
    # Too close
    confidence[depth_m < optimal_range[0]] = 0.5
    
    # Optimal range
    # confidence stays 1.0
    
    # Degraded range (linear falloff)
    degraded_mask = depth_m > optimal_range[1]
    confidence[degraded_mask] = 1.0 - (depth_m[degraded_mask] - optimal_range[1]) / (max_range - optimal_range[1])
    
    # Clip and handle invalid
    confidence = np.clip(confidence, 0, 1)
    confidence[depth_image == 0] = 0
    
    return confidence
```

### 5. Combined Confidence Estimator

```python
import numpy as np
import cv2
from collections import deque

class D435ConfidenceEstimator:
    """
    Combines multiple heuristics to estimate per-pixel depth confidence.
    
    Output: 0.0 (no confidence) to 1.0 (high confidence)
    """
    
    def __init__(self, history_size=5, depth_scale=0.001):
        self.temporal = deque(maxlen=history_size)
        self.depth_scale = depth_scale
        
        # Weights for combining confidence sources
        self.weights = {
            'validity': 0.3,      # Has valid depth
            'temporal': 0.3,      # Stable over time
            'distance': 0.2,      # Within optimal range
            'edge': 0.2,          # Not at occlusion boundary
        }
    
    def estimate(self, depth_image, rgb_image=None):
        """
        Estimate confidence for each pixel.
        
        Args:
            depth_image: Raw depth frame (uint16, values in mm or depth units)
            rgb_image: Optional RGB frame for edge detection
            
        Returns:
            confidence: Float32 array, same shape as depth, values 0-1
        """
        # Resize RGB to match depth if needed
        if rgb_image is not None and rgb_image.shape[:2] != depth_image.shape:
            rgb_image = cv2.resize(rgb_image, (depth_image.shape[1], depth_image.shape[0]))
        
        # 1. Validity confidence
        validity = (depth_image > 0).astype(np.float32)
        
        # 2. Temporal confidence
        self.temporal.append(depth_image.astype(np.float32))
        if len(self.temporal) >= 2:
            stack = np.array(self.temporal)
            valid_stack = np.where(stack > 0, stack, np.nan)
            with np.errstate(all='ignore'):
                variance = np.nanvar(valid_stack, axis=0)
            temporal = 1.0 / (1.0 + variance / 100.0)
            temporal = np.nan_to_num(temporal, nan=0.0)
        else:
            temporal = validity.copy()
        
        # 3. Distance confidence
        depth_m = depth_image.astype(np.float32) * self.depth_scale
        distance = np.ones_like(depth_m)
        distance[depth_m < 0.3] = 0.5  # Too close
        degraded = (depth_m > 1.0) & (depth_m <= 3.0)
        distance[degraded] = 1.0 - (depth_m[degraded] - 1.0) / 2.0
        distance[depth_m > 3.0] = 0.1  # Too far
        distance[depth_image == 0] = 0
        
        # 4. Edge confidence
        if rgb_image is not None:
            gray = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            kernel = np.ones((5, 5), np.uint8)
            edge_zone = cv2.dilate(edges, kernel, iterations=2)
            edge_conf = np.where(edge_zone > 0, 0.5, 1.0).astype(np.float32)
            edge_conf[depth_image == 0] = 0
        else:
            edge_conf = validity.copy()
        
        # Combine with weights
        confidence = (
            self.weights['validity'] * validity +
            self.weights['temporal'] * temporal +
            self.weights['distance'] * distance +
            self.weights['edge'] * edge_conf
        )
        
        # Normalize to 0-1
        confidence = confidence / sum(self.weights.values())
        confidence[depth_image == 0] = 0  # Ensure invalid stays 0
        
        return confidence.astype(np.float32)
```

## Advanced Mode: DSSecondPeakThreshold

The D435 VPU calculates best and second-best stereo matches. This parameter controls how different they must be:

```python
import pyrealsense2 as rs
import json

def configure_d435_advanced_mode(pipeline, second_peak_threshold=400):
    """
    Configure D435 stereo matching strictness.
    
    Higher threshold = stricter matching = fewer false positives but more holes
    Lower threshold = more permissive = better fill but potential errors
    
    Range: 0-1023
    Default varies by visual preset
    """
    device = pipeline.get_active_profile().get_device()
    
    # Check if advanced mode is supported
    if not device.is(rs.camera_info.advanced_mode):
        print("Advanced mode not supported on this device")
        return False
    
    advanced_mode = rs.rs400_advanced_mode(device)
    
    # Enable advanced mode if not already enabled
    if not advanced_mode.is_enabled():
        advanced_mode.toggle_advanced_mode(True)
        # Need to reconnect after enabling
        print("Advanced mode enabled - reconnect camera")
        return False
    
    # Get current settings
    settings = json.loads(advanced_mode.serialize_json())
    
    # Modify second peak threshold
    # This is nested in the depth table
    if 'parameters' in settings:
        settings['parameters']['secondPeakThreshold'] = second_peak_threshold
    
    # Apply settings
    advanced_mode.load_json(json.dumps(settings))
    
    return True
```

## Raw IR Stereo Access (DIY Disparity)

For full control, access raw IR frames and compute your own disparity/confidence:

```python
import pyrealsense2 as rs
import cv2
import numpy as np

def setup_raw_stereo_streams(config):
    """Enable raw IR stereo streams for custom processing"""
    # Left IR
    config.enable_stream(rs.stream.infrared, 1, 848, 480, rs.format.y8, 30)
    # Right IR  
    config.enable_stream(rs.stream.infrared, 2, 848, 480, rs.format.y8, 30)
    # Depth (for comparison)
    config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)

def compute_disparity_with_confidence(left_ir, right_ir):
    """
    Compute disparity and confidence using OpenCV stereo matching.
    
    Uses left-right consistency check for confidence estimation.
    """
    # Create stereo matchers
    left_matcher = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=96,  # Must be divisible by 16
        blockSize=5,
        P1=8 * 3 * 5**2,
        P2=32 * 3 * 5**2,
        disp12MaxDiff=1,
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=32
    )
    
    right_matcher = cv2.ximgproc.createRightMatcher(left_matcher)
    
    # Compute disparities
    left_disp = left_matcher.compute(left_ir, right_ir)
    right_disp = right_matcher.compute(right_ir, left_ir)
    
    # WLS filter for confidence
    wls_filter = cv2.ximgproc.createDisparityWLSFilter(left_matcher)
    wls_filter.setLambda(8000)
    wls_filter.setSigmaColor(1.5)
    
    filtered_disp = wls_filter.filter(left_disp, left_ir, disparity_map_right=right_disp)
    
    # Get confidence map from WLS filter
    confidence = wls_filter.getConfidenceMap()
    
    return filtered_disp, confidence
```

## Sensor Fusion Architecture Ideas

### Option 1: Weighted Average
Simple approach - combine depths weighted by confidence:

```python
def fuse_weighted_average(depth1, conf1, depth2, conf2):
    """Fuse two depth maps using confidence-weighted average"""
    # Normalize confidences
    total_conf = conf1 + conf2 + 1e-6  # Avoid division by zero
    w1 = conf1 / total_conf
    w2 = conf2 / total_conf
    
    # Weighted average
    fused = w1 * depth1 + w2 * depth2
    
    # Combined confidence (could use max, product, or other)
    fused_conf = np.maximum(conf1, conf2)
    
    return fused, fused_conf
```

### Option 2: Confidence-Gated Selection
Use highest-confidence sensor per pixel:

```python
def fuse_winner_takes_all(depth1, conf1, depth2, conf2):
    """Select depth from highest confidence sensor per pixel"""
    use_sensor1 = conf1 >= conf2
    
    fused = np.where(use_sensor1, depth1, depth2)
    fused_conf = np.where(use_sensor1, conf1, conf2)
    
    return fused, fused_conf
```

### Option 3: Outlier-Aware Fusion
If sensors disagree significantly, trust neither:

```python
def fuse_with_outlier_rejection(depth1, conf1, depth2, conf2, 
                                 max_disagreement_mm=50):
    """Fuse with rejection when sensors disagree"""
    # Both must have valid depth
    both_valid = (depth1 > 0) & (depth2 > 0)
    
    # Check agreement
    disagreement = np.abs(depth1.astype(float) - depth2.astype(float))
    agree = disagreement < max_disagreement_mm
    
    # Where they agree, use weighted average
    total_conf = conf1 + conf2 + 1e-6
    weighted_avg = (conf1 * depth1 + conf2 * depth2) / total_conf
    
    # Where they disagree, use higher confidence (or reject both)
    use_sensor1 = conf1 > conf2
    disagreed_choice = np.where(use_sensor1, depth1, depth2)
    disagreed_conf = np.where(use_sensor1, conf1, conf2) * 0.5  # Reduce confidence
    
    # Combine
    fused = np.where(both_valid & agree, weighted_avg, 
                     np.where(both_valid, disagreed_choice,
                              np.where(depth1 > 0, depth1, depth2)))
    
    fused_conf = np.where(both_valid & agree, np.maximum(conf1, conf2),
                          np.where(both_valid, disagreed_conf,
                                   np.where(depth1 > 0, conf1, conf2)))
    
    return fused, fused_conf
```

## Potential Secondary Sensors

### iPad LiDAR (via network streaming)
- Technology: dToF (direct Time of Flight)
- Range: 0-5m
- Strengths: Works on reflective/transparent surfaces, true confidence values
- Weaknesses: Lower resolution, requires network streaming setup
- See: `docs/ipad-depth-sensor.md`

### Intel RealSense L515 (if acquired)
- Technology: Solid-state LiDAR
- Has native confidence stream (`rs.stream.confidence`)
- Better for close range (0.25-9m)
- Less affected by ambient light

### Stereo from RGB cameras
- Use two webcams or iPhone stereo cameras
- Compute disparity with OpenCV
- Complements IR stereo (works in different lighting)

## Implementation Priorities

1. **Phase 1**: Implement D435 confidence estimation (temporal + distance)
2. **Phase 2**: Test with grasp planning - does confidence improve success rate?
3. **Phase 3**: Add secondary sensor if D435 confidence proves insufficient
4. **Phase 4**: Implement full sensor fusion pipeline

## Open Questions

- [ ] What confidence threshold should reject a grasp pose?
- [ ] How to handle sensor registration (alignment between D435 and secondary sensor)?
- [ ] Is temporal filtering fast enough for real-time grasp planning?
- [ ] Should we fuse at depth level or point cloud level?

## References

- [D435 confidence discussion - GitHub #13357](https://github.com/IntelRealSense/librealsense/issues/13357)
- [Accessing confidence stream - GitHub #3185](https://github.com/IntelRealSense/librealsense/issues/3185)
- [Depth Post-Processing for D400](https://dev.intelrealsense.com/docs/depth-post-processing)
- [Tuning D400 cameras](https://dev.intelrealsense.com/docs/tuning-depth-cameras-for-best-performance)
