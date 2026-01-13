# App Bundle Size Optimization Guide

This document describes the app bundle size reduction strategies for the Access Ability Arm macOS application.

## Initial State (Before Optimization)

**Original Bundle Size**: 2.2 GB

### Size Breakdown (Original)
Analysis of the bundled packages revealed:
- **app.zip**: 749 MB (application code and dependencies)
- **polars**: 228 MB (unused - pulled by ultralytics)
- **jaxlib**: 222 MB (unused - pulled by mediapipe)
- **torch**: 198 MB (required for YOLO)
- **opencv-python**: 124 MB (required, but can be optimized)
- **mediapipe**: 82 MB (required for face tracking)

## Optimization Strategies Implemented

### 1. Switch to opencv-python-headless ✅

**Rationale**: The headless version excludes GUI support (Qt, GTK), which we don't need since the app uses Flet for the GUI.

**Changes**:
- Modified `requirements.txt`: `opencv-python` → `opencv-python-headless`
- No code changes required (same API)

**Size Savings**:
- Before: 119 MB (opencv-python + opencv-contrib-python)
- After: 99 MB (opencv-python-headless)
- **Savings: ~20 MB**

**Risk**: None - we don't use cv2.imshow or other GUI functions

### 2. Enable Flet Package Cleanup ✅

**Changes**:
- Added `--cleanup-packages` flag to Makefile build command
- Removes unnecessary package metadata and cached files

**Estimated Savings**: ~50-100 MB

### 3. Attempted: Exclude Unused Heavy Dependencies ⚠️

**Issue**: The `--cleanup-package-files` flag in Flet has a bug (TypeError when passing multiple patterns)

**Workaround**: Filed for future fix; using `--cleanup-packages` instead

**Target Dependencies**:
- polars (228 MB) - used by ultralytics but not needed for basic inference
- jax/jaxlib (222 MB) - used by mediapipe but optional for face tracking

**Potential Future Savings**: ~450 MB if successfully excluded

## Advanced Optimization Options (Not Yet Implemented)

### Option A: Switch to ONNX Runtime for YOLO Inference

**Potential Savings**: ~323 MB

**Details**:
- **Current**: PyTorch 2.9.1 (340 MB installed)
- **Alternative**: ONNX Runtime (17 MB)
- **Size Reduction**: 95% smaller runtime

**Requirements**:
1. Export YOLO model to ONNX format:
   ```python
   from ultralytics import YOLO
   model = YOLO('yolo11n-seg.pt')
   model.export(format='onnx', opset=12, imgsz=[640,640])
   ```

2. Replace PyTorch inference code with ONNX Runtime:
   ```python
   import onnxruntime as ort
   session = ort.InferenceSession('yolo11n-seg.onnx', 
                                   providers=['CPUExecutionProvider'])
   ```

3. Update `requirements.txt`:
   - Remove: `ultralytics`, `torch`, `torchvision`
   - Add: `onnxruntime` (17 MB)
   - Manually implement YOLO post-processing (NMS, bbox decoding)

**Trade-offs**:
- ✅ Massive size reduction (323 MB)
- ✅ Faster CPU inference in some cases
- ❌ Requires code refactoring
- ❌ Lose Ultralytics high-level API
- ❌ Need to manually implement pre/post-processing
- ❌ May lose some features (training, model updates)

**References**:
- [Ultralytics ONNX Export Docs](https://docs.ultralytics.com/integrations/onnx/)
- [Official ONNX Runtime Example](https://github.com/ultralytics/ultralytics/blob/main/examples/YOLOv8-ONNXRuntime/main.py)

### Option B: PyTorch Mobile Lite Interpreter

**Status**: Deprecated - PyTorch recommends ExecuTorch instead

**Details**:
- PyTorch Mobile Lite can reduce binary size by up to 70%
- Requires model conversion and custom build
- No longer actively maintained by PyTorch team

**Not Recommended**: Use ONNX Runtime instead for better support and smaller size

### Option C: Remove Optional Dependencies via pip --no-deps

**Concept**: Install packages without dependencies, then manually install only what's needed

**Example**:
```bash
pip install ultralytics --no-deps
pip install torch torchvision numpy matplotlib opencv-python-headless \
    pyyaml pillow psutil requests scipy ultralytics-thop
# Skip: polars (saves 228 MB)
```

**Risk**: High - may break at runtime if polars is actually used

**Status**: Not recommended without extensive testing

### Option D: Custom PyTorch Build (Advanced)

**Concept**: Compile PyTorch from source with only needed operators

**Requirements**:
- Build PyTorch from source
- Use selective operator registration
- Configure build to exclude unused modules

**Complexity**: Very High
- Requires C++ compilation
- Build time: 1-2 hours
- Platform-specific build configurations
- Difficult to maintain

**Estimated Savings**: 50-100 MB (15-30% reduction)

**Not Recommended**: Complexity outweighs benefits

## Current State (After Initial Optimizations)

### Implemented Changes
1. ✅ opencv-python → opencv-python-headless (20 MB saved)
2. ✅ Added --cleanup-packages flag
3. ✅ Added camera permissions to Info.plist (fixes crash)

### Expected Bundle Size
- Original: 2.2 GB
- After cleanup: ~1.8-2.0 GB
- **Estimated Reduction**: 200-400 MB (9-18%)

## Realistic Size Expectations

### Minimum Achievable Size (Current Architecture)
**~1.5 GB** with all current optimizations + manual package exclusion

**Breakdown**:
- Core app + Python runtime: ~500 MB
- PyTorch + torchvision: ~340 MB
- MediaPipe (without jax): ~82 MB
- opencv-python-headless: ~99 MB
- Ultralytics (without polars): ~3 MB
- Other dependencies: ~100 MB
- Flet/Flutter framework: ~300 MB

### Target Size of 250 MB: Not Achievable

**Why 250 MB is unrealistic**:
- PyTorch alone: 340 MB (required for YOLO)
- Flet/Flutter framework: ~300 MB (GUI)
- MediaPipe: 82 MB (face tracking)
- **Minimum core dependencies: ~700+ MB**

**To reach 250 MB would require**:
1. Complete architecture rewrite using ONNX Runtime
2. Alternative GUI framework (native or lightweight)
3. Elimination of all heavy ML frameworks
4. Likely loss of significant functionality

## Recommended Path Forward

### Short-term (Current Release)
1. ✅ Use opencv-python-headless
2. ✅ Enable --cleanup-packages
3. ✅ Fix camera permissions
4. **Target**: 1.8-2.0 GB bundle

### Medium-term (Next Release)
1. Investigate ONNX Runtime migration for YOLO
2. Test mediapipe without jax/jaxlib dependency
3. Manual package exclusion testing
4. **Target**: 1.0-1.5 GB bundle

### Long-term (Major Refactor)
1. Full ONNX Runtime implementation
2. Evaluate alternative face tracking (lighter than MediaPipe)
3. Consider native GUI alternatives to Flet
4. **Target**: 500-800 MB bundle

## Package Dependency Analysis

### Dependency Chain

```
Application
├── flet (GUI framework)
│   ├── flet-desktop
│   ├── flet-web
│   └── Flutter SDK (~300 MB)
├── ultralytics (YOLO)
│   ├── torch (~340 MB) ⚠️ LARGE
│   ├── torchvision (~7 MB)
│   ├── polars (~228 MB) ⚠️ OPTIONAL/UNUSED
│   ├── opencv-python-headless (~99 MB)
│   ├── numpy (~21 MB)
│   └── other deps (~50 MB)
├── mediapipe (face tracking)
│   ├── jax (~1 MB)
│   ├── jaxlib (~222 MB) ⚠️ OPTIONAL/UNUSED
│   └── numpy (shared)
└── pyrealsense2 (optional, manual install)
```

### Key Insights
- **torch** (340 MB): Largest dependency, required for YOLO
- **polars** (228 MB): Pulled by ultralytics, likely unused for inference
- **jaxlib** (222 MB): Pulled by mediapipe, may be optional
- **Total "unnecessary"**: ~450 MB (polars + jaxlib)

## Testing Checklist

Before deploying size-optimized builds:

- [ ] Test YOLO object detection works correctly
- [ ] Test MediaPipe face tracking works correctly
- [ ] Test RealSense camera integration (if available)
- [ ] Test standard webcam fallback
- [ ] Test camera permission dialog appears
- [ ] Test mode switching (T key)
- [ ] Test all robotic arm controls
- [ ] Verify no crashes on launch
- [ ] Check console for missing dependency errors
- [ ] Measure actual bundle size
- [ ] Test on clean macOS install

## Build Commands

### Current Build (Optimized)
```bash
make clean
make package-macos
```

### Measure Bundle Size
```bash
du -sh build/macos/Access\ Ability\ Arm.app
```

### Analyze Package Contents
```bash
du -sh build/macos/Access\ Ability\ Arm.app/Contents/Resources/app.zip
unzip -l build/macos/Access\ Ability\ Arm.app/Contents/Resources/app.zip | grep -E "polars|jax|torch" | head -20
```

## References

- [Flet Build Documentation](https://flet.dev/docs/reference/cli/build/)
- [Ultralytics ONNX Export](https://docs.ultralytics.com/integrations/onnx/)
- [ONNX Runtime Python](https://onnxruntime.ai/docs/get-started/with-python.html)
- [PyTorch Binary Size Discussion](https://github.com/pytorch/pytorch/issues/17621)
- [MediaPipe Installation](https://developers.google.com/mediapipe/framework/getting_started/install)

## Conclusion

**Current realistic target**: 1.5-2.0 GB with low-risk optimizations

**Aggressive target**: 1.0 GB with ONNX Runtime migration (requires code refactoring)

**Original goal of 250 MB**: Not achievable without fundamental architecture changes that would compromise functionality

The most impactful next step is migrating YOLO inference to ONNX Runtime, which would save ~323 MB with moderate implementation effort.
