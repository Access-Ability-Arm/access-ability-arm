# Building a Depth-Based Grasp Planning System for Assistive Robotics

> **Recommendation**: Start with a Python-native architecture using Open3D for perception and either AnyGrasp or GraspNet-1Billion for grasp planning. This approach achieves a working prototype in your 1-month timeline, leverages your team's Python/AI expertise without requiring ROS experience, and provides a clear migration path to ROS2 when you need advanced features.

This recommendation is based on analysis of your specific constraints: a 2-person team with strong AI/coding skills and mechanical engineering expertise but no ROS experience, testing on Windows and macOS platforms, and aggressive timeline targeting a working prototype in approximately 1 month. The assistive robotics use case for ALS patients demands reliability over complexity, making a focused Python implementation more appropriate than a full robotics middleware stack initially.

## Table of Contents

1. [Current State-of-the-Art in Grasp Planning](#current-state-of-the-art-in-grasp-planning)
2. [Architecture Comparison: Open3D vs ROS2 vs Python Toolkits](#architecture-comparison)
3. [Step-by-Step Technical Implementation](#step-by-step-technical-implementation)
4. [Realistic Timeline Assessment](#realistic-timeline-assessment)
5. [Grasp Quality Metrics](#grasp-quality-metrics)
6. [Integration Pipeline](#integration-pipeline)
7. [Calibration Procedures](#calibration-procedures)

---

## Current State-of-the-Art in Grasp Planning

The field has converged around learning-based approaches that operate directly on point clouds from depth cameras, with **AnyGrasp** and **GraspNet-1Billion** representing the current state-of-the-art for your use case. These methods achieve 90-93% success rates on novel household objects—approaching human-level performance—and work explicitly with the RealSense D435 depth camera you're using.

### AnyGrasp (Primary Recommendation)

Published in IEEE Transactions on Robotics in 2023:
- **93.3% success rate** on 300+ unseen objects with real-time performance
- Explicit RealSense D435 compatibility
- Generates 7-DOF dense grasp poses with temporal smoothness for tracking moving objects
- Trained on real perception data to handle depth sensor noise robustly
- Commercial SDK requires license registration (typically 2-3 days approval)
- Fastest path to production-quality grasping with minimal implementation effort

### GraspNet-1Billion (Open-Source Alternative)

Excellent fully open-source alternative from the same Shanghai Jiao Tong University research group:
- Built on a dataset of **1 billion grasp poses** across 190 scenes and 88 household objects
- RealSense-specific pre-trained models that work out of the box
- Architecture uses PointNet++ encoders with decoupled approach direction and operation parameters
- **85-90% success rates** with clear documentation and active community support

### Contact-GraspNet (NVIDIA)

- Novel 4-DOF contact-based representation (reduced from 6-DOF for computational efficiency)
- Training in just 40 hours (versus a week for competitors) on 17 million simulated grasps from ACRONYM dataset
- Efficient end-to-end inference in a single forward pass
- PyTorch implementations and ROS wrappers readily available

### Traditional Geometric Approaches

**GPD (Grasp Pose Detection)**:
- 93% success in dense clutter without requiring training
- Uses pre-trained CNN to classify sampled grasp candidates from point clouds
- Requires more manual tuning

**Dex-Net 2.0 (Berkeley)**:
- Operates on depth images rather than full point clouds
- 93% success on known objects with 0.8-second planning time
- Unique advantage of CPU-viable operation

### Recent 2024-2025 Developments

- Language-driven grasping
- Enhanced scale handling for small objects
- NeRF-based methods for multi-view reconstruction
- AnyGrasp SDK updates: dense prediction mode and Python 3.10 support
- Scale-Balanced GraspNet improvements for detecting small objects (utensils, medication bottles)

---

## Architecture Comparison

The architectural decision fundamentally determines whether you'll achieve a working prototype in 1 month or spend that time learning frameworks.

### Why Python-Native with Open3D Succeeds

Open3D provides:
- Native RealSense SDK v2 integration (v0.12+) without separate librealsense installation
- Works seamlessly on Linux, macOS, and Windows
- Integrates directly with your existing Python stack
- **Learning curve: 3-7 days** to productivity (vs 3-4 weeks for ROS2)

Your entire existing stack—Flet GUI, pyrealsense2, xarm-python-sdk, and RF-DETR—connects through direct Python imports without middleware or message passing overhead.

**Data Flow**:
```
RF-DETR → Object masks
    ↓
RealSense → Depth frames
    ↓
Open3D → Point clouds with mask-based cropping
    ↓
Grasp Detection → Object-specific point clouds
    ↓
xarm-python-sdk → Execute selected grasp
```

All components run in a single Python process with shared memory.

### Why ROS2 Fails the 1-Month Timeline

ROS2 represents the industry standard for production robotics systems, but for a team without ROS experience targeting a 1-month prototype, ROS2 would consume your entire timeline learning concepts rather than building your application.

**Conceptual Overhead**:
- Publishers/subscribers for inter-process communication
- Services/actions for synchronous operations
- Transforms (TF2) for coordinate frame management
- Launch files for system initialization
- Colcon build system

**Platform Constraints**:
- macOS support effectively died after ROS2 Foxy (May 2021)
- Windows has Tier 2 support—functional but limited

**Learning Curve**: 3-4 weeks to basic productivity vs 3-7 days for Open3D

### Detailed Architecture Comparison Matrix

| Criterion | Open3D Python-Native | ROS2 | Robotics Toolkit |
|-----------|---------------------|------|------------------|
| **Time to prototype** | 2-3 weeks (90% confidence) | 6-8 weeks minimum (30% confidence) | 3-4 weeks (85% confidence) |
| **Learning curve** | 3-7 days | 3-4 weeks | 1-2 weeks |
| **Platform support** | Win/Mac/Linux | Linux only (Mac dropped) | Win/Mac/Linux |
| **Existing stack integration** | Direct Python imports | Requires wrappers | Direct Python |
| **pyrealsense2** | Native support | Use realsense-ros | Direct |
| **xarm-python-sdk** | Direct calls | Use xarm_ros2 | Direct |
| **Flet GUI** | Same process | Separate process | Same process |
| **RF-DETR** | Native PyTorch | Needs wrapper | Native |
| **Grasp planning** | Integrate external | MoveIt grasps | Implement custom |
| **Motion planning** | Basic IK | MoveIt2 excellent | Robotics Toolbox |
| **Simulation** | PyBullet separate | Gazebo integrated | PyBullet |
| **Community size** | Medium | Very large | Small-Medium |
| **1-month verdict** | **Recommended** | Too slow | Viable |

### Recommended Hybrid Strategy

**Phase 1 (Month 1): Python-native prototype**
```
Open3D (perception + point cloud processing)
+ AnyGrasp SDK or GraspNet-1Billion (grasp planning)
+ Robotics Toolbox or xArm IK (kinematics)
+ xarm-python-sdk (control)
+ Flet (GUI)
+ PyBullet (simulation/testing)
```

**Phase 2 (Months 2-6): Selective ROS2 integration**
- Wrap Python perception module as ROS2 node
- Add MoveIt2 for sophisticated motion planning
- Switch to xarm_ros2 for standardized control interfaces
- Migration cost: 2-4 weeks of refactoring (can proceed incrementally)

---

## Step-by-Step Technical Implementation

### Week 1: Establish the Perception Pipeline

1. **Install dependencies**:
   ```bash
   pip install open3d pyrealsense2
   ```

2. **Configure RealSense D435**:
   - Resolution: 848×480 @ 30 FPS
   - Preset: Medium Density
   - Working range: 0.3-3.0m

3. **Implement filter pipeline**:
   - Decimation filter
   - Spatial filter (alpha=0.5, delta=20)
   - Temporal filter (alpha=0.4)
   - Hole filling

4. **Integrate RF-DETR segmentation**:
   - Generate object masks
   - Apply masks to depth image (zero out background)
   - Convert to 3D point cloud using RealSense intrinsics

5. **Point cloud preprocessing with Open3D**:
   ```python
   # Statistical outlier removal
   cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
   # Voxel downsampling if needed
   # Normal estimation for grasp planning
   ```

6. **Test objects**: cups, bottles, utensils, phone, medication containers

**Deliverable**: Clean, segmented point clouds for target objects with RF-DETR masks correctly applied.

### Week 2: Implement Grasp Detection

1. **Apply for AnyGrasp SDK license** (2-3 days approval) while setting up GraspNet-1Billion as backup

2. **GraspNet-1Billion setup**:
   - Clone repository
   - Compile PointNet++ operators with CUDA support
   - Download RealSense-specific pre-trained model

3. **AnyGrasp configuration**:
   - Set workspace boundaries (tight as possible)
   - Enable collision detection flag
   - Use `object_mask` mode for RF-DETR integration
   - Use `dense_grasp` flag for more candidates

4. **Grasp quality scoring**:
   ```python
   quality = 1.5 * antipodal_score + 1.0 * force_closure + 0.5 * com_score
   quality *= (1.0 if collision_free else 0.0)
   ```

5. **Visualize grasp candidates** using Open3D geometry rendering

**Deliverable**: Ranked grasp poses for each target object type with quality scores >0.7.

### Week 3: Bridge to Robot Control with Calibration

1. **Hand-eye calibration (ArUco marker method)**:
   - Print 6×6 ArUco board (50mm markers)
   - Mount rigidly on table
   - Move robot to 15-20 diverse poses
   - Capture images and record robot poses
   - Use OpenCV's `calibrateHandEye()` with Tsai method:
   ```python
   R_cam2base, t_cam2base = cv2.calibrateHandEye(
       R_gripper2base, t_gripper2base,
       R_target2cam, t_target2cam,
       method=cv2.CALIB_HAND_EYE_TSAI
   )
   ```

2. **Expected calibration accuracy**: 2-5mm translation, 1-2° rotation

3. **Coordinate transformation chain**:
   ```
   pixel (u,v) + depth → 3D camera coordinates (RealSense intrinsics)
                       → robot base frame (calibration matrix)
                       → end effector commands (xArm SDK, millimeters)
   ```

4. **Motion planning state machine**:
   - Approach (100mm above target, 100mm/s)
   - Descend to grasp position
   - Close gripper
   - Lift (200mm up)
   - Transport
   - Release

5. **Test with soft objects first** at 10-20% speed

**Deliverable**: Complete pick-and-place sequences on soft test objects.

### Week 4: Safety Systems and Integration Polish

1. **Hardware emergency stop**: Large red mushroom button hardwired to xArm controller

2. **Software safety**:
   - Space bar E-stop
   - Watchdog timer (500ms timeout)

3. **ISO 13482 limits for personal care robots**:
   - Maximum contact force: 50N (transient), 25N (sustained)
   - Maximum speed near humans: 250mm/s
   - Workspace speed: up to 500mm/s
   - Approach speed: 100mm/s
   - Acceleration: 500mm/s²
   - Jerk: 2000mm/s³

4. **Safe workspace boundaries**:
   - Define 3D boundaries
   - Define patient exclusion zone (cylindrical region)
   - Check before every motion command

5. **Flet GUI integration**:
   - Camera view with RF-DETR overlay
   - Detected objects with confidence scores
   - Selected grasp pose visualization
   - Manual object selection and grasp confirmation
   - Real-time status (idle/perceiving/planning/executing/error)
   - Clear emergency stop button

**Deliverable**: Fully integrated system with 70%+ success rate, safe motion, and comprehensive GUI.

---

## Realistic Timeline Assessment

### Achievable in Month 1 (HIGH Confidence)

**Core perception and planning pipeline**:
- RealSense D435 point cloud acquisition with proper filtering
- RF-DETR integration for object segmentation
- Grasp pose generation using pre-trained models
- Coordinate transformation from camera to robot base
- Visualization of all intermediate steps

**Robot control and execution**:
- Hand-eye calibration (2-5mm accuracy)
- Basic IK using xArm SDK
- Simple pick-and-place state machine
- Testing on regular household objects (matte surfaces)
- Operation at reduced speeds (50-100mm/s)

**Safety and interface**:
- Hardware E-stop with software backup
- Workspace boundary enforcement
- Force and speed limits
- Basic Flet GUI for object selection and status

**Success metrics**:
- 70%+ grasp success on 10 test objects
- Safe operation with E-stop verified
- Full pipeline demonstrated end-to-end
- Clear documentation

### Defer to Months 2-3 (MEDIUM Difficulty)

- Fine-tuning grasp quality metrics for specific gripper
- Multiple grasp strategies (top-down, side-grasp, pinch)
- Advanced collision detection with full arm geometry
- Grasp failure recovery with automatic retry
- Sophisticated trajectory planning with obstacle avoidance
- Dynamic replanning during execution
- MoveIt2 integration for complex scenarios

**Challenging objects**:
- Transparent containers (difficult for depth cameras)
- Highly reflective surfaces
- Deformable objects requiring force sensing
- Small objects (<2cm)

### Defer to Months 4-6+ (HIGH Difficulty)

- Custom training on specific objects and gripper
- Sim-to-real transfer learning
- Reinforcement learning for grasp optimization
- Dynamic object grasping (moving targets)
- Bimanual manipulation
- Compliant control for feeding assistance
- Force-based insertion tasks
- FDA clearance / CE marking for medical device status

---

## Grasp Quality Metrics

### Force Closure

The gold standard—a grasp achieves force closure when it can resist arbitrary external wrenches through contact forces alone. Check computationally by verifying that contact forces span the entire wrench space using convex hull algorithms on the Grasp Wrench Space (GWS).

### Epsilon Quality (Dex-Net)

Measures robustness to uncertainty in object pose, friction coefficients, and contact positions. Directly correlates with real-world success rates.

### Antipodal Score

Verifies that surface normals at contact points face opposite directions with the gripper axis bisecting them. For parallel-jaw grippers, check that the angle between surface normals and the gripper closing direction exceeds 80°.

### Distance to Center of Mass

Grasps closer to the COM generally provide better stability and resist toppling during lifting.

### Combined Quality Function

```python
quality = 1.5 * antipodal_score + 1.0 * force_closure + 0.5 * com_score
quality *= (1.0 if collision_free else 0.0)
```

The collision check acts as a binary gate—any grasp causing gripper-object or gripper-scene collision receives zero quality.

### Gripper-Specific Considerations

**Parallel-jaw grippers (UFactory Lite 6)**:
- Prioritize antipodal grasps with friction cone validation
- Use μ=0.5 (friction coefficient) for typical household objects
- Most grippers provide 50-150mm range
- May struggle with very large (>120mm diameter) or very small (<15mm) objects

**Vacuum grippers**:
- Evaluate surface planarity using PCA on local point cloud patches
- Require minimum 300mm² surface area within suction cup radius
- Work best on horizontal or gently sloped surfaces (<30° from vertical)
- Avoid porous materials and wet surfaces

---

## Integration Pipeline

### Complete Data Flow

```python
# 1. RF-DETR produces instance masks
object_mask = rf_detr_output['masks'][object_id]

# 2. RealSense provides aligned depth (ensure alignment)
align = rs.align(rs.stream.color)
aligned_frames = align.process(frames)

# 3. Apply mask to depth image
depth_masked = depth_image.copy()
depth_masked[~object_mask] = 0

# 4. Convert to 3D point cloud
# Use RealSense pointcloud() API or Open3D's create_from_rgbd_image()

# 5. Clean point cloud
cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

# 6. Feed to grasp planner (AnyGrasp or GraspNet)
# Returns: list of candidate grasps with transformation matrices, widths, scores

# 7. Transform grasp to robot coordinates
grasp_base = T_base_camera @ grasp_camera

# 8. Execute motion plan state machine
```

### Coordinate Frame Conventions

- **RealSense optical frame**: Z forward (into scene), Y down, X right
- **Robot base frame**: Typically Z up, X forward
- **End-effector frame**: Depends on mounting

Use visualization in Open3D to verify transforms—render coordinate axes at each frame.

### Common Integration Issues

| Issue | Solution |
|-------|----------|
| Unit mismatches | Open3D uses meters, xArm SDK uses millimeters |
| Rotation conventions | Choose one format (quaternions, Euler, rotation matrices) and convert consistently |
| Timestamp synchronization | Use `rs.align()` in pyrealsense2 for depth/color alignment |

---

## Calibration Procedures

### Hand-Eye Calibration (ArUco Method)

**Budget**: Full day for initial calibration; recalibrate monthly or after physical changes.

1. **Prepare ArUco board**:
   ```python
   board = cv2.aruco.GridBoard_create(6, 6, 0.05, 0.01, aruco_dict)
   # Print at actual size (50mm markers)
   ```

2. **Mount board rigidly** on table (must remain completely stationary)

3. **Collect data**:
   - Move robot through 15-20 diverse poses
   - At each pose: record end-effector pose + capture image

4. **Solve calibration**:
   ```python
   R_cam2base, t_cam2base = cv2.calibrateHandEye(
       R_gripper2base, t_gripper2base,
       R_target2cam, t_target2cam,
       method=cv2.CALIB_HAND_EYE_TSAI
   )
   ```

5. **Validate**:
   - Place marker at known position
   - Detect with camera
   - Transform to robot coordinates
   - Command robot to that position
   - Measure error with calipers (should be <5mm)

### Expected Accuracy

- **Translation error**: 2-5mm
- **Rotation error**: 1-2°

If errors exceed 5mm, recalibrate with more diverse poses or check camera mount rigidity.

### RealSense Depth Calibration

The D435 ships factory-calibrated. Only recalibrate if:
- Systematic depth errors observed (e.g., all measurements 2% off)
- After drops or impacts
- Obvious accuracy degradation

Use Intel RealSense Viewer's "On-Chip Calibration" tool (15 seconds, point at blank wall).

---

## Summary

For a 1-month prototype with your team's constraints (Python/AI expertise, no ROS experience, macOS/Windows development):

1. **Use Open3D** for perception and point cloud processing
2. **Use AnyGrasp SDK** (or GraspNet-1Billion as backup) for grasp planning
3. **Use xarm-python-sdk** directly for robot control with built-in IK
4. **Integrate with your existing** Flet GUI and RF-DETR segmentation
5. **Defer ROS2** to months 3-6 when you need MoveIt2 or multi-robot support

The Python-native approach achieves a working end-to-end demo by week 2, with weeks 3-4 dedicated to calibration, safety systems, and integration polish. Target 70%+ grasp success on household objects with safe, predictable motion.
