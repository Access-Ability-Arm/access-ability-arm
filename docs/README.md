# Documentation Index

## Active Documentation

Essential docs for working with the project:

| Document | Description |
|----------|-------------|
| [installation.md](installation.md) | Setup and installation guide |
| [monorepo.md](monorepo.md) | Package structure and architecture |
| [known-issues.md](known-issues.md) | Current bugs and workarounds |
| [ufactory_studio.md](ufactory_studio.md) | UFactory Lite6 arm setup |
| [new-features.md](new-features.md) | Feature roadmap and status |
| [grasp_planning_report.md](grasp_planning_report.md) | Open3D grasp planning implementation plan |

## Hardware Documentation

Setup and specifications for hardware components:

| Document | Description |
|----------|-------------|
| [realsense-setup.md](hardware/realsense-setup.md) | RealSense installation and troubleshooting |
| [realsense-d435-specs.md](hardware/realsense-d435-specs.md) | D435 specs, resolutions, visual presets |
| [ipad-depth-sensor.md](hardware/ipad-depth-sensor.md) | iPad LiDAR as backup depth sensor |
| [depth-sensor-alternatives.md](hardware/depth-sensor-alternatives.md) | Comparison of depth sensor options |
| [windows-distribution.md](hardware/windows-distribution.md) | Windows packaging and distribution |
| [windows-user-readme.md](hardware/windows-user-readme.md) | Windows user guide |

## Research & Planning

Exploration, analysis, and implementation research:

| Document | Description |
|----------|-------------|
| [sensor-fusion-brainstorming.md](research/sensor-fusion-brainstorming.md) | Multi-sensor fusion strategies |
| [pick-and-place-strategy.md](research/pick-and-place-strategy.md) | Pick and place implementation guide |
| [segmentation-smoothing-robotics.md](research/segmentation-smoothing-robotics.md) | Real-time segmentation smoothing |
| [spatial-smoothing-implementation.md](research/spatial-smoothing-implementation.md) | Spatial smoothing details |
| [depth-validation-implementation.md](research/depth-validation-implementation.md) | Depth validation approach |
| [detection-logging.md](research/detection-logging.md) | Detection stability analysis |

## Archive

Historical documentation preserved for reference.

### Decisions Made

Past architectural decisions and comparisons:

- [gui-framework-comparison.md](archive/decisions/gui-framework-comparison.md) - Why we chose Flet
- [client-server-architecture-plan.md](archive/decisions/client-server-architecture-plan.md) - Daemon architecture decision
- [daemon-architecture-implementation-plan.md](archive/decisions/daemon-architecture-implementation-plan.md) - Original daemon plan

### Completed Work

Documentation for finished implementations:

- [daemon-phase1-complete.md](archive/completed/daemon-phase1-complete.md) - Daemon implementation summary
- [size-optimization.md](archive/completed/size-optimization.md) - App bundle optimization
- [build-size-analysis.md](archive/completed/build-size-analysis.md) - Build size analysis results

### Abandoned

Plans that were explored but not pursued:

- [tauri-migration-plan.md](archive/abandoned/tauri-migration-plan.md) - Tauri migration (abandoned for Flet)
- [why-tauri-is-small.md](archive/abandoned/why-tauri-is-small.md) - Tauri size analysis
- [application-builds.md](archive/abandoned/application-builds.md) - Old build docs (pre-Flet)
