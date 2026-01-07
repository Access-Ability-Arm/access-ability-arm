# Depth Sensor Alternatives Research

This document provides verified specifications for depth sensor alternatives to the Intel RealSense, compiled from official sources and manufacturer documentation.

## Summary Comparison

| Device | Price | Depth Resolution | Accuracy | Range | Technology | Status |
|--------|-------|-----------------|----------|-------|------------|--------|
| **Intel RealSense D455** | $419 | 1280x720 | <2% @ 4m | 0.4-6m | Active IR Stereo | Available |
| **Intel RealSense D435** | ~$280 | 1280x720 | <2% @ 2m | 0.1-10m | Active IR Stereo | Available |
| **Orbbec Femto Bolt** | $418 | 1024x1024 | <11mm + 0.1% | 0.25-5.5m | iToF (MS tech) | Available |
| **Luxonis OAK-D Pro** | $299 | 800P stereo | ~1% @ 1-2m | 0.2-12m | Active Stereo | Available |
| **Structure Sensor Mark II** | ~$399 | 1280x960 | Not specified | 0.3-5m+ | IR Stereo | Available |
| **Azure Kinect DK** | N/A | 1024x1024 | Sub-cm | 0.25-5.5m | ToF | **Discontinued** |
| **iPad Pro LiDAR** | N/A | 256x192 | ~1cm @ <5m | 0.5-5m | dToF | Via ARKit |

## Detailed Specifications

### Intel RealSense D455 (Current Recommendation)

**Price**: $419 (official Intel store)

**Key Specifications**:
- Depth Resolution: 1280x720 @ up to 90 fps
- Optimal Resolution: 848x480
- Depth Accuracy: <2% at 4 meters
- Range: 0.4m - 6m optimal
- Baseline: 95mm (longer = better long-range accuracy)
- RGB: Global shutter (matches depth sensor)
- IMU: Integrated 6-axis
- USB: 3.1 Gen 1

**Advantages**:
- 2x the depth accuracy of D435 at distance
- Global shutter on RGB (reduces motion blur)
- Well-documented SDK (librealsense)
- Already integrated in our codebase

**Disadvantages**:
- Minimum depth: 0.4m (vs 0.1m for D435)
- Requires sudo on macOS (our daemon solves this)

**Sources**: [Intel RealSense Store](https://store.intelrealsense.com/buy-intel-realsense-depth-camera-d455.html), [Compare Depth Cameras](https://www.intelrealsense.com/compare-depth-cameras/)

---

### Intel RealSense D435/D435i

**Price**: ~$280-334 (D435i with IMU)

**Key Specifications**:
- Depth Resolution: 1280x720 @ up to 90 fps
- Depth Accuracy: <2% at 2 meters
- Range: 0.1m - 10m
- Baseline: ~50mm
- RGB: Rolling shutter
- IMU: Only on D435i variant

**Advantages**:
- Lower minimum depth (0.1m) - good for close work
- Widely available, mature product

**Disadvantages**:
- Half the long-range accuracy of D455
- RGB rolling shutter can cause artifacts

**Sources**: [Intel RealSense Comparison](https://support.intelrealsense.com/hc/en-us/community/posts/1500000161261-D455-vs-D435)

---

### Orbbec Femto Bolt (Azure Kinect Replacement)

**Price**: $418

**Key Specifications**:
- **Depth Technology**: iToF (identical to Azure Kinect DK)
- **Depth Resolution**: Multiple modes:
  - WFOV Unbinned: 1024x1024 @ 15 fps, range 0.25-2.21m
  - WFOV Binned: 512x512 @ 30 fps, range 0.25-2.88m
  - NFOV Unbinned: 640x576 @ 30 fps, range 0.5-3.86m
  - NFOV Binned: 320x288 @ 30 fps, range 0.5-5.46m
- **Depth Accuracy**: 
  - Standard deviation: ≤17mm
  - System error: <11mm + 0.1% of distance
- **RGB**: 4K (3840x2160) @ 30 fps with HDR
- **FOV**: 120° x 120° (WFOV mode)
- **Power**: 7.7-8.7W via USB-C

**Advantages**:
- Official Microsoft-recommended Azure Kinect replacement
- Uses identical Microsoft ToF technology
- K4A Wrapper available for easy migration from Azure Kinect code
- Higher quality RGB with HDR support
- More compact than Azure Kinect

**Disadvantages**:
- Higher power consumption (needs powered USB hub)
- ToF has limited range compared to stereo
- Less community support than RealSense

**Sources**: [Orbbec Femto Bolt](https://www.orbbec.com/products/tof-camera/femto-bolt/), [Orbbec Store](https://store.orbbec.com/products/femto-bolt), [Comparison with Azure Kinect](https://www.orbbec.com/documentation/comparison-with-azure-kinect-dk/)

---

### Luxonis OAK-D Pro

**Price**: $299

**Key Specifications**:
- **Technology**: Active stereo with IR dot projector
- **Depth Resolution**: 800P (OV9282/OV9782 sensors)
- **Depth Accuracy**: ~1% at 1-2 meters
- **Range**: 
  - MinZ: 20cm (400P extended) to 70cm (800P)
  - Ideal: 70cm - 12m
- **Baseline**: 7.5cm
- **On-device AI**: 4 TOPS (Intel Myriad X VPU)
- **RGB**: 12MP IMX378
- **Power**: Up to 7.5W

**Advantages**:
- Integrated AI processing (run YOLO on-device)
- IR dot projector improves accuracy on textureless surfaces
- Long range capability (up to 12m)
- Competitive price

**Disadvantages**:
- Stereo depth oscillates with distance (inherent limitation)
- Less accurate than ToF for sub-centimeter needs
- Different SDK (DepthAI) - would require new integration

**Sources**: [OAK-D Pro Shop](https://shop.luxonis.com/products/oak-d-pro), [Depth Accuracy Docs](https://docs.luxonis.com/hardware/platform/depth/depth-accuracy/), [Luxonis Forum](https://discuss.luxonis.com/d/3540-oak-d-pro-depth-accuracy-specifications)

---

### Structure Sensor Mark II

**Price**: ~$399 (at launch, 2019)

**Key Specifications**:
- **Depth Resolution**: 1280x960
- **Range**: 0.3m - 5m+
- **FOV**: 59° x 46°
- **Technology**: IR stereo (works outdoors)
- **Size**: 109mm x 18mm x 24mm
- **Weight**: 65g
- **Features**: 
  - 160° ultra-wide tracking camera
  - 6-axis IMU
  - On-device depth processing (NU3000 ASIC)

**Advantages**:
- Very compact and lightweight
- Works outdoors (stereo-based)
- Designed for iPad mounting

**Disadvantages**:
- Primarily designed for iOS (limited cross-platform support)
- Some users report unresolved depth quality issues
- Focused on 3D scanning, not real-time robotics

**Sources**: [Structure Sensor Specs](https://stage-static.structure.io/structure-sensor/specs), [3D Scan Expert Review](https://3dscanexpert.com/structure-sensor-mark-ii-features-higher-resolution-outdoor-scanning/)

---

### Azure Kinect DK (Discontinued)

**Status**: Discontinued October 2023 - **DO NOT PURCHASE**

**Original Specifications** (for reference):
- Depth: 1024x1024 ToF
- RGB: 4K (3840x2160)
- Sub-centimeter accuracy
- 7-microphone array

**Replacement**: Orbbec Femto Bolt (uses same Microsoft ToF technology)

**Sources**: [Microsoft Ending Azure Kinect](https://redmondmag.com/articles/2023/08/17/microsoft-ending-azure-kinect.aspx), [GitHub Issue #1971](https://github.com/microsoft/Azure-Kinect-Sensor-SDK/issues/1971)

---

## Recommendations for Access Ability Arm

### Primary: Intel RealSense D455 (Current)
Our current choice remains optimal:
- <2% accuracy at 4m is excellent for arm positioning
- Mature SDK already integrated
- USB 3.1 for fast data transfer
- $419 price point is reasonable

### Backup Option: Orbbec Femto Bolt ($418)
If RealSense becomes unavailable:
- ToF provides consistent accuracy (not distance-dependent like stereo)
- K4A wrapper eases integration
- Same price point as D455
- Higher power requirements

### Budget Alternative: Luxonis OAK-D Pro ($299)
If cost is a concern:
- On-device AI could offload detection from main system
- Longer range (up to 12m)
- Would require new SDK integration (DepthAI)

### Mobile/Portable: iPad Pro LiDAR
See [ipad-depth-sensor.md](ipad-depth-sensor.md) for details on using iPad as a backup depth sensor via ARKit streaming.

## Integration Considerations

| Factor | RealSense D455 | Femto Bolt | OAK-D Pro |
|--------|----------------|------------|-----------|
| SDK | librealsense | Orbbec SDK / K4A | DepthAI |
| Python Support | Excellent | Good | Excellent |
| macOS Support | Requires sudo | Unknown | Good |
| Our Current Code | Integrated | Moderate effort | Major effort |
| Community Size | Large | Growing | Medium |

## Recommended Enhancement: Dual-Sensor Depth Fusion

### Motivation

**Core use case requirement**: Users will regularly interact with metal utensils, glasses, and shiny surfaces (eating, drinking, handling everyday items). The RealSense D455's active IR stereo struggles with these reflective surfaces due to specular reflections disrupting the projected pattern.

A dual-sensor approach combining RealSense D455 + Orbbec Femto Bolt is recommended to provide reliable depth sensing for the full range of expected objects.

### Why Combine These Two Sensors?

| Scenario | D455 (Active IR Stereo) | Femto Bolt (iToF) | Fused Result |
|----------|------------------------|-------------------|--------------|
| **Reflective/shiny objects** | Poor (specular reflection) | Better (phase-based) | Use ToF |
| **Textureless surfaces** | Needs IR pattern | Excellent | Use ToF |
| **Long range (3-6m)** | Good | Out of range | Use stereo |
| **Close range (<0.4m)** | Below min range | Excellent | Use ToF |
| **Bright lighting** | More tolerant | IR interference | Use stereo |
| **Multi-path interference** | Less affected | Susceptible | Use stereo |
| **General accuracy** | Distance-dependent | Consistent | Weighted blend |

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Dual Depth Sensor Fusion System                                │
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Intel RealSense │         │  Orbbec Femto    │             │
│  │  D455            │         │  Bolt            │             │
│  │  (USB 3.0)       │         │  (USB 3.0)       │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
│           ▼                            ▼                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Frame Synchronization                                   │   │
│  │  • Hardware trigger (if available) or software sync     │   │
│  │  • Timestamp alignment within 10ms tolerance            │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Spatial Registration                                    │   │
│  │  • Extrinsic calibration (rigid transform between sensors)│  │
│  │  • Project both depth maps to common coordinate frame    │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Confidence Estimation (per-pixel)                       │   │
│  │                                                          │   │
│  │  D455 confidence factors:                                │   │
│  │  • IR pattern visibility (texture score)                 │   │
│  │  • Stereo matching confidence                            │   │
│  │  • Distance (accuracy degrades with range²)              │   │
│  │                                                          │   │
│  │  Femto Bolt confidence factors:                          │   │
│  │  • Signal amplitude (IR return strength)                 │   │
│  │  • Phase unwrapping quality                              │   │
│  │  • Distance (within valid range 0.25-5.5m)               │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Depth Fusion Algorithm                                  │   │
│  │                                                          │   │
│  │  For each pixel:                                         │   │
│  │  1. If only one sensor has valid depth → use it          │   │
│  │  2. If depths agree (within threshold) → weighted avg    │   │
│  │  3. If depths disagree significantly → use higher conf   │   │
│  │  4. If both low confidence → mark as uncertain           │   │
│  │                                                          │   │
│  │  fused_depth = (d455_conf * d455_depth +                 │   │
│  │                 bolt_conf * bolt_depth) /                │   │
│  │                (d455_conf + bolt_conf)                   │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Temporal Filtering                                      │   │
│  │  • Kalman filter for depth stability                     │   │
│  │  • Outlier rejection across frames                       │   │
│  │  • Motion compensation using IMU data                    │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Output: High-Precision Fused Depth Map                  │   │
│  │  • Resolution: 1280x720 (D455 native)                    │   │
│  │  • Confidence map included                               │   │
│  │  • ~20-25 fps (limited by fusion processing)             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

1. **Hardware Setup**
   - Mount both sensors on rigid bracket with known baseline
   - Use separate USB 3.0 controllers (avoid bandwidth contention)
   - Powered USB hub for Femto Bolt (8W requirement)

2. **Calibration**
   - Intrinsic calibration for each sensor (factory or custom)
   - Extrinsic calibration using checkerboard visible to both sensors
   - Store calibration as 4x4 transformation matrix

3. **Software Integration**
   - Extend `camera_daemon_socket.py` to support dual sensors
   - Add Orbbec SDK alongside librealsense
   - Implement fusion as separate processing stage

4. **Fusion Algorithm** (Python pseudocode)
   ```python
   def fuse_depth(d455_depth, d455_conf, bolt_depth, bolt_conf, threshold=0.05):
       """Fuse two depth maps with confidence weighting."""
       fused = np.zeros_like(d455_depth)
       confidence = np.zeros_like(d455_depth)
       
       # Both valid and agree
       agree_mask = (d455_depth > 0) & (bolt_depth > 0) & \
                    (np.abs(d455_depth - bolt_depth) < threshold * d455_depth)
       
       # Weighted average where they agree
       total_conf = d455_conf + bolt_conf + 1e-6
       fused[agree_mask] = (d455_conf[agree_mask] * d455_depth[agree_mask] +
                            bolt_conf[agree_mask] * bolt_depth[agree_mask]) / \
                           total_conf[agree_mask]
       confidence[agree_mask] = np.minimum(d455_conf[agree_mask] + bolt_conf[agree_mask], 1.0)
       
       # Disagree - use higher confidence
       disagree_mask = (d455_depth > 0) & (bolt_depth > 0) & ~agree_mask
       use_d455 = disagree_mask & (d455_conf >= bolt_conf)
       use_bolt = disagree_mask & (bolt_conf > d455_conf)
       fused[use_d455] = d455_depth[use_d455]
       fused[use_bolt] = bolt_depth[use_bolt]
       confidence[disagree_mask] = 0.5  # Lower confidence when sensors disagree
       
       # Only one valid
       only_d455 = (d455_depth > 0) & (bolt_depth <= 0)
       only_bolt = (bolt_depth > 0) & (d455_depth <= 0)
       fused[only_d455] = d455_depth[only_d455]
       fused[only_bolt] = bolt_depth[only_bolt]
       confidence[only_d455] = d455_conf[only_d455] * 0.8
       confidence[only_bolt] = bolt_conf[only_bolt] * 0.8
       
       return fused, confidence
   ```

5. **Reflective Object Handling**
   - Detect low-confidence regions in D455 (specular reflections)
   - Automatically weight Femto Bolt higher in these regions
   - Use RGB segmentation to identify metallic/shiny materials

### Cost-Benefit Analysis

| Factor | Value |
|--------|-------|
| **Hardware Cost** | $419 (D455) + $418 (Femto Bolt) = **$837** |
| **Development Time** | ~2-3 weeks for basic fusion |
| **Performance Impact** | ~20-25 fps (down from 30 fps) |
| **Accuracy Improvement** | Estimated 30-50% reduction in depth errors on reflective surfaces |
| **Complexity** | Moderate (calibration, sync, two SDKs) |

### Priority: High

Given that users will regularly interact with reflective objects (utensils, glasses, shiny surfaces), dual-sensor fusion should be implemented before production deployment to ensure reliable depth sensing across all expected use cases.

### References

- [Depth Sensor Fusion Survey (IEEE)](https://ieeexplore.ieee.org/document/8794308)
- [Multi-Sensor Depth Fusion for Robotics](https://arxiv.org/abs/1903.04013)
- [Orbbec SDK Python](https://github.com/orbbec/pyorbbecsdk)

---

## Conclusion

**Recommended setup**: Intel RealSense D455 + Orbbec Femto Bolt with depth fusion.

Given the core use case of assisting users with metal utensils, glasses, and other reflective everyday objects, a dual-sensor approach is recommended for production. The $837 total hardware cost and moderate development effort are justified by the significant improvement in depth reliability for reflective surfaces.

For prototyping and development, the D455 alone is sufficient, but plan for dual-sensor integration before user deployment.
