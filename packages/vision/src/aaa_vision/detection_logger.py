"""
Detection Logger
Logs object detection data for post-session analysis of tracking stability
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class DetectionLogger:
    """Logs detection data to analyze tracking stability and flickering"""

    def __init__(self, log_dir: str = "logs/detections", enabled: bool = False):
        """
        Initialize detection logger

        Args:
            log_dir: Directory to store log files
            enabled: Whether logging is enabled (default False to avoid performance impact)
        """
        self.enabled = enabled
        self.log_dir = Path(log_dir)
        self.log_file = None
        self.frame_count = 0
        self.session_start = None

        # Track object IDs across frames for lifecycle analysis
        self.object_ids = {}  # (class_name, approx_center) -> unique_id
        self.next_id = 0

        if self.enabled:
            self._initialize_session()

    def _initialize_session(self):
        """Create new log file for this session"""
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"detections_{timestamp}.jsonl"
        self.session_start = time.time()
        self.frame_count = 0

        # Write session metadata
        with open(self.log_file, 'w') as f:
            metadata = {
                "type": "session_start",
                "timestamp": timestamp,
                "start_time": self.session_start
            }
            f.write(json.dumps(metadata) + '\n')

        print(f"✓ Detection logging enabled: {self.log_file}")

    def log_frame(self,
                  raw_detections: List[tuple],
                  tracked_detections: List[tuple],
                  raw_boxes: List[list],
                  tracked_boxes: List[list]):
        """
        Log detections for a single frame

        Args:
            raw_detections: List of (class_name, center) from detector
            tracked_detections: List of (class_name, center) after tracking
            raw_boxes: List of [x1, y1, x2, y2] for raw detections
            tracked_boxes: List of [x1, y1, x2, y2] for tracked detections
        """
        if not self.enabled:
            return

        self.frame_count += 1
        timestamp = time.time() - self.session_start

        # Assign IDs to tracked objects (approximate matching)
        tracked_ids = []
        for class_name, center in tracked_detections:
            obj_id = self._get_or_create_id(class_name, center)
            tracked_ids.append(obj_id)

        # Build frame data
        frame_data = {
            "type": "frame",
            "frame": self.frame_count,
            "timestamp": round(timestamp, 3),
            "raw_count": len(raw_detections),
            "tracked_count": len(tracked_detections),
            "raw_detections": [
                {
                    "class": class_name,
                    "center": list(center),
                    "box": box
                }
                for (class_name, center), box in zip(raw_detections, raw_boxes)
            ],
            "tracked_detections": [
                {
                    "id": obj_id,
                    "class": class_name,
                    "center": list(center),
                    "box": box
                }
                for obj_id, (class_name, center), box in zip(tracked_ids, tracked_detections, tracked_boxes)
            ]
        }

        # Write to file (JSONL format - one JSON object per line)
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(frame_data) + '\n')

    def _get_or_create_id(self, class_name: str, center: tuple) -> int:
        """
        Get or create unique ID for object
        Uses approximate matching based on class and position
        """
        # Round center to grid (50px) for approximate matching
        grid_size = 50
        grid_center = (
            round(center[0] / grid_size) * grid_size,
            round(center[1] / grid_size) * grid_size
        )

        key = (class_name, grid_center)

        if key not in self.object_ids:
            self.object_ids[key] = self.next_id
            self.next_id += 1

        return self.object_ids[key]

    def close(self):
        """Close logging session"""
        if not self.enabled or self.log_file is None:
            return

        # Write session end marker
        with open(self.log_file, 'a') as f:
            end_data = {
                "type": "session_end",
                "timestamp": time.time() - self.session_start,
                "total_frames": self.frame_count
            }
            f.write(json.dumps(end_data) + '\n')

        print(f"✓ Detection log saved: {self.log_file} ({self.frame_count} frames)")

    def enable(self):
        """Enable logging mid-session"""
        if not self.enabled:
            self.enabled = True
            self._initialize_session()

    def disable(self):
        """Disable logging mid-session"""
        if self.enabled:
            self.close()
            self.enabled = False
