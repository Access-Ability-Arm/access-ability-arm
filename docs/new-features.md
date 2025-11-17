# New Features Roadmap

This document tracks potential improvements and new features for the Access Ability Arm project, prioritized by impact and implementation effort.

## Current Status

**Vision Pipeline:** RF-DETR Seg for object detection + MediaPipe for face tracking
**Performance:** 25-30 FPS on current hardware
**Primary Challenge:** Frame-to-frame segmentation jitter affecting grasp stability

---

## Priority 1: Temporal Smoothing with ByteTrack

**Status:** Planned
**Estimated Effort:** 1-2 weeks
**Impact:** High - Improves grasp success rate from ~70% to 90%+

### Overview
ByteTrack provides object tracking across frames, maintaining temporal identity and reducing segmentation jitter. This is the single highest-impact improvement for manipulation stability.

### Why ByteTrack Over Newer Alternatives?

**Recent SOTA alternatives considered:**
- **Deep-OC-SORT** (2024) - Current MOT benchmark leader, 31px vs 114px tracking error
- **StrongSORT** (2023) - Enhanced DeepSORT with top MOT17/MOT20 scores
- **BoT-SORT** (2022) - Better accuracy than ByteTrack but slower
- **OC-SORT** (2023) - 700+ FPS, better for non-linear motion

**Why we're choosing ByteTrack:**
1. **Perfect fit for stationary objects:** Our use case (objects on tables) doesn't need complex non-linear motion models or appearance matching that Deep-OC-SORT/StrongSORT provide
2. **Fastest implementation:** 0.2s inference, simplest codebase, well-documented
3. **Proven in production robotics:** Used by RightHand Robotics and similar assistive systems
4. **Occlusion handling via low-confidence tracking:** Exactly what we need when arm obscures objects
5. **Integrated with Ultralytics:** Works seamlessly with our RF-DETR/YOLO pipeline
6. **Speed over benchmark accuracy:** We need responsiveness for arm control, not MOT20 leaderboard scores

**When to upgrade to Deep-OC-SORT:** If we start tracking many similar objects (5+ cups), experience identity switches, or need to track through long occlusions (>2 seconds). For now, ByteTrack's simplicity and speed better match our requirements.

**Comparison table:**

| Tracker | Speed | Accuracy | Occlusion | Implementation | Stationary Objects |
|---------|-------|----------|-----------|----------------|-------------------|
| ByteTrack | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ **BEST** |
| Deep-OC-SORT | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| BoT-SORT | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| OC-SORT | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| StrongSORT | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

### Benefits
- Reduces identity switches by 30-50%
- Maintains object tracking through brief occlusions
- Only 1-2ms overhead (fits in 30 FPS budget)
- Solves primary problem: 5-10 pixel jitter → 3-8mm position uncertainty

### Implementation Plan
1. Add ByteTrack dependency to requirements.txt
2. Integrate with RF-DETR detection pipeline
3. Configure for stationary objects:
   - `track_thresh=0.6` (higher for stationary scenes)
   - `track_buffer=60` (2 seconds at 30 FPS)
   - `match_thresh=0.7` (IoU threshold)
4. Add exponential moving average (alpha=0.97) for bounding boxes/masks
5. Implement track ID persistence in detection manager

### Configuration Parameters
```python
tracker = ByteTrack(
    track_thresh=0.6,      # Higher for stationary objects
    track_buffer=60,       # 2 seconds at 30 FPS
    match_thresh=0.7,      # IoU threshold
    frame_rate=30
)

# Temporal smoothing
alpha = 0.97  # High for stationary scenes (0.95-0.98 recommended)
```

### References
- ByteTrack (ECCV 2022): https://arxiv.org/abs/2110.06864
- Deep-OC-SORT (2024): https://arxiv.org/abs/2302.11813
- OC-SORT (CVPR 2023): https://arxiv.org/abs/2203.14360
- BoT-SORT (2022): https://arxiv.org/abs/2206.14651
- See `docs/segmentation-smoothing-robotics.md` Section 1 for details

---

## Priority 2: Morphological Spatial Smoothing

**Status:** In Progress
**Estimated Effort:** 2-3 days
**Impact:** Medium-High - Immediate visual improvement, 40-60% boundary smoothing

### Overview
Fast, CPU-based boundary refinement using morphological operations. Runs in 2-3ms with no GPU required.

### Benefits
- Smooths jagged segmentation boundaries
- Fills small holes in masks
- Removes noise and spurious detections
- Battle-tested, zero dependencies (OpenCV built-in)
- Works on CPU—no GPU transfer overhead

### Implementation Plan
1. Create `SpatialSmoother` class in `packages/vision/src/aaa_vision/`
2. Implement adaptive kernel sizing based on object area
3. Integrate into detection manager pipeline
4. Add configuration options to `config.yaml`

### Algorithm
```python
# Closing (fills holes) + Opening (removes noise)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
```

### Adaptive Kernel Sizing
- Small objects (<1% frame area): 3×3 kernel, 1 iteration
- Medium objects (1-10% frame area): 5×5 kernel, 2 iterations
- Large objects (>10% frame area): 7×7 kernel, 3 iterations

### Configuration Parameters
```yaml
vision:
  spatial_smoothing:
    enabled: true
    kernel_shape: "ellipse"  # ellipse, rectangle, cross
    small_object_kernel: 3
    medium_object_kernel: 5
    large_object_kernel: 7
    iterations: 2
```

### References
- See `docs/segmentation-smoothing-robotics.md` Section 2.1 for details

---

## Priority 3: Depth Discontinuity Detection

**Status:** Planned
**Estimated Effort:** 1-2 weeks
**Impact:** Medium - Leverages existing RealSense hardware for edge cases

### Overview
Use **lightweight depth edge detection** to validate and refine RGB segmentation boundaries, especially for transparent/textureless objects. Focus on fast gradient-based methods, not computationally expensive point cloud segmentation.

### Why Not Full Point Cloud Segmentation?

**Considered alternatives (NOT recommended):**
- ❌ **Open3D RANSAC plane segmentation**: 10-100ms overhead (too slow)
- ❌ **Point cloud clustering (DBSCAN)**: Computationally expensive for real-time
- ❌ **Kornia GPU operations**: No benefit for single-frame processing, adds complexity

**Our approach (fast and effective):**
- ✅ **Sobel depth gradients**: <2ms, detects discontinuities
- ✅ **2D depth edge detection**: Lightweight, real-time capable
- ✅ **Selective point cloud use**: Only for failure cases (transparent objects)

**Research basis (2024):** Hybrid 2D-3D approaches outperform pure point cloud methods for real-time grasping. RGB segmentation + depth validation achieves 82%+ success rates while maintaining real-time performance.

### Benefits
- Detects transparent objects (glass, plastic) invisible to RGB
- Resolves textureless objects (white dish on white table)
- Validates RGB boundaries with physical depth discontinuities
- Adds <2ms overhead—maintains 30+ FPS performance

### Implementation Plan
1. Create `DepthValidator` class
2. Implement Sobel-based depth gradient detection (fast, <2ms)
3. Add depth-RGB boundary cross-validation
4. Integrate with existing RealSense daemon architecture
5. **Optional:** Add Open3D for specific failure cases only (transparent objects)

### Algorithm
```python
# Fast depth discontinuity detection (<2ms)
# NOT: Full point cloud segmentation (10-100ms)
depth_grad = cv2.Sobel(depth_map, cv2.CV_32F, 1, 1, ksize=3)
depth_edges = (np.abs(depth_grad) > threshold).astype(np.uint8)

# Dilate to create boundary regions
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
boundary_regions = cv2.dilate(depth_edges, kernel, iterations=1)

# Cross-validate RGB boundaries against depth discontinuities
# If RGB boundary aligns with depth edge: high confidence
# If RGB boundary has no depth support: flag for review

# Optional: Point cloud fallback for specific failures
# Only use Open3D when:
# 1. RGB segmentation fails (no detections)
# 2. Object is known to be transparent/reflective
# 3. User explicitly requests 3D reconstruction
```

### Performance Budget
- Sobel depth gradients: <1ms
- Edge detection & dilation: <1ms
- Boundary cross-validation: <0.5ms
- **Total: <2ms** (maintains 30+ FPS)

### Configuration Parameters
```yaml
vision:
  depth_validation:
    enabled: true
    discontinuity_threshold: 0.03  # 3cm for manipulation distances
    min_confidence: 0.5
    fallback_to_rgb: true  # Use RGB-only if depth quality poor
    use_point_cloud: false  # Enable only for transparent object handling
```

### References
- See `docs/segmentation-smoothing-robotics.md` Section 3 for details
- 2024 research: RGB-based OptiGrasp achieves 82.3% success with fast 2D methods

---

## Future Enhancements (Deferred)

### TensorRT Optimization
**Effort:** 1-2 weeks  
**Impact:** 3-27× inference speedup

Optimize RF-DETR with TensorRT for production deployment. Defer until pipeline is stable and performance profiling identifies inference as bottleneck.

- Convert PyTorch model to ONNX format
- Optimize with TensorRT builder (FP16/INT8 quantization)
- Profile with NVIDIA Nsight Systems
- Target: 60+ FPS on Jetson platforms

### Optical Flow Motion Compensation (MCMA)
**Effort:** 2-3 weeks  
**Impact:** 4.25% temporal consistency improvement

Motion-Corrected Moving Average warps previous frames using optical flow before temporal averaging. Overkill for stationary objects—consider only if tracking moving objects.

### SegFix Boundary Refinement
**Effort:** 3-4 weeks (requires training)  
**Impact:** Model-agnostic boundary improvement

Post-processing that refines any segmentation model's boundaries. Requires training boundary and direction prediction networks. Save for v2 when precision grasping becomes critical.

### DFormerv2 RGB-D Fusion
**Effort:** 4-6 weeks (requires retraining)  
**Impact:** State-of-the-art RGB-D segmentation

Replace current pipeline with unified RGB-D architecture. Significant effort, consider only if current approach hits accuracy ceiling.

---

## Implementation Timeline

### Phase 1: Quick Wins (Weeks 1-2)
- ✅ Document new features roadmap
- 🔄 Implement morphological spatial smoothing
- 🔄 Add configuration options
- 🔄 Validate performance (2-3ms overhead target)

### Phase 2: Temporal Stability (Weeks 3-4)
- ⏳ Integrate ByteTrack tracking
- ⏳ Implement exponential moving average
- ⏳ Tune parameters for stationary objects
- ⏳ Measure grasp stability improvement

### Phase 3: Depth Integration (Weeks 5-6)
- ⏳ Add depth discontinuity detection
- ⏳ Implement RGB-depth boundary validation
- ⏳ Test with transparent/textureless objects
- ⏳ Optimize parallel processing

### Phase 4: Optimization (Weeks 7-8)
- ⏳ Profile complete pipeline
- ⏳ Adaptive parameter tuning
- ⏳ TensorRT optimization (if needed)
- ⏳ Real-world manipulation testing

---

## Success Metrics

### Performance Targets
- **Frame Rate:** Maintain 25-30 FPS (current baseline)
- **Latency:** Total pipeline <33ms for 30 FPS
- **Temporal Consistency:** Mask IoU >0.95 between consecutive frames
- **Boundary Accuracy:** F-score >0.85 within 2-pixel tolerance

### Manipulation Targets
- **Grasp Success Rate:** >90% for known objects (vs. ~70% baseline)
- **Position Stability:** <3mm jitter at 0.5-1.5m manipulation distance
- **Identity Switches:** <5% for tracked objects (vs. 30-50% baseline)

---

## Notes

- All features prioritize real-time performance (30+ FPS)
- Implementation tested on existing hardware (RealSense D455 camera)
- Parameters tuned for assistive robotics use case (stationary objects)
- See `docs/segmentation-smoothing-robotics.md` for detailed research and algorithms

**Last Updated:** 2025-11-17
