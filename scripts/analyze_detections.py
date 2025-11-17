#!/usr/bin/env python3
"""
Detection Log Analyzer
Analyzes detection logs to measure tracking stability and flickering

Usage:
    python scripts/analyze_detections.py logs/detections/detections_20250116_123456.jsonl
    python scripts/analyze_detections.py logs/detections/  # Analyze latest log
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


class DetectionAnalyzer:
    """Analyzes detection logs to calculate stability metrics"""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.frames = []
        self.metadata = {}
        self._load_log()

    def _load_log(self):
        """Load log file"""
        print(f"Loading log: {self.log_file}")

        with open(self.log_file, 'r') as f:
            for line in f:
                data = json.loads(line)

                if data['type'] == 'session_start':
                    self.metadata['start'] = data
                elif data['type'] == 'session_end':
                    self.metadata['end'] = data
                elif data['type'] == 'frame':
                    self.frames.append(data)

        print(f"✓ Loaded {len(self.frames)} frames")

    def analyze(self):
        """Run full analysis and print report"""
        print("\n" + "="*60)
        print("DETECTION STABILITY ANALYSIS")
        print("="*60)

        self._analyze_session_summary()
        print()
        self._analyze_object_lifetimes()
        print()
        self._analyze_flickering()
        print()
        self._analyze_position_stability()
        print()
        self._analyze_detection_vs_tracking()

    def _analyze_session_summary(self):
        """Print session overview"""
        print("SESSION SUMMARY")
        print("-" * 60)

        total_frames = len(self.frames)
        duration = self.frames[-1]['timestamp'] if self.frames else 0
        fps = total_frames / duration if duration > 0 else 0

        print(f"Total frames:     {total_frames}")
        print(f"Duration:         {duration:.1f}s")
        print(f"Average FPS:      {fps:.1f}")

    def _analyze_object_lifetimes(self):
        """Analyze how long objects persist"""
        print("OBJECT LIFETIMES")
        print("-" * 60)

        # Track first and last appearance of each object ID
        object_appearances = defaultdict(list)

        for frame in self.frames:
            frame_num = frame['frame']
            for obj in frame['tracked_detections']:
                obj_id = obj['id']
                object_appearances[obj_id].append(frame_num)

        if not object_appearances:
            print("No tracked objects found")
            return

        # Calculate lifetimes
        lifetimes = []
        for obj_id, frames_seen in object_appearances.items():
            lifetime = max(frames_seen) - min(frames_seen) + 1
            lifetimes.append(lifetime)

        print(f"Total unique objects:  {len(lifetimes)}")
        print(f"Average lifetime:      {statistics.mean(lifetimes):.1f} frames")
        print(f"Median lifetime:       {statistics.median(lifetimes):.1f} frames")
        print(f"Min lifetime:          {min(lifetimes)} frames")
        print(f"Max lifetime:          {max(lifetimes)} frames")

        # Lifetime distribution
        short_lived = sum(1 for lt in lifetimes if lt < 5)
        medium_lived = sum(1 for lt in lifetimes if 5 <= lt < 30)
        long_lived = sum(1 for lt in lifetimes if lt >= 30)

        print(f"\nLifetime distribution:")
        print(f"  < 5 frames:          {short_lived} ({100*short_lived/len(lifetimes):.1f}%)")
        print(f"  5-29 frames:         {medium_lived} ({100*medium_lived/len(lifetimes):.1f}%)")
        print(f"  >= 30 frames:        {long_lived} ({100*long_lived/len(lifetimes):.1f}%)")

    def _analyze_flickering(self):
        """Analyze flickering (rapid appear/disappear)"""
        print("FLICKERING ANALYSIS")
        print("-" * 60)

        # Track consecutive appearances
        object_runs = defaultdict(list)  # obj_id -> list of (start_frame, end_frame)
        object_current_run = {}  # obj_id -> start_frame

        for frame in self.frames:
            frame_num = frame['frame']
            current_ids = {obj['id'] for obj in frame['tracked_detections']}

            # Start new runs for objects that appeared
            for obj_id in current_ids:
                if obj_id not in object_current_run:
                    object_current_run[obj_id] = frame_num

            # End runs for objects that disappeared
            disappeared = set(object_current_run.keys()) - current_ids
            for obj_id in disappeared:
                start = object_current_run[obj_id]
                object_runs[obj_id].append((start, frame_num - 1))
                del object_current_run[obj_id]

        # Close remaining runs
        if self.frames:
            last_frame = self.frames[-1]['frame']
            for obj_id, start in object_current_run.items():
                object_runs[obj_id].append((start, last_frame))

        # Analyze runs
        total_runs = sum(len(runs) for runs in object_runs.values())
        flicker_runs = 0  # Runs that lasted < 5 frames
        stable_runs = 0   # Runs that lasted >= 5 frames

        for obj_id, runs in object_runs.items():
            for start, end in runs:
                duration = end - start + 1
                if duration < 5:
                    flicker_runs += 1
                else:
                    stable_runs += 1

        print(f"Total object runs:     {total_runs}")
        print(f"Flickering runs (<5f): {flicker_runs} ({100*flicker_runs/total_runs:.1f}%)")
        print(f"Stable runs (>=5f):    {stable_runs} ({100*stable_runs/total_runs:.1f}%)")

        # Objects with multiple runs (reappearing)
        multi_run_objects = sum(1 for runs in object_runs.values() if len(runs) > 1)
        print(f"\nObjects that flickered (reappeared):")
        print(f"  {multi_run_objects} / {len(object_runs)} ({100*multi_run_objects/len(object_runs):.1f}%)")

    def _analyze_position_stability(self):
        """Analyze position variance for stable objects"""
        print("POSITION STABILITY")
        print("-" * 60)

        # Track positions for each object
        object_positions = defaultdict(list)

        for frame in self.frames:
            for obj in frame['tracked_detections']:
                obj_id = obj['id']
                center = tuple(obj['center'])
                object_positions[obj_id].append(center)

        # Calculate variance for objects with >10 frames
        variances = []
        for obj_id, positions in object_positions.items():
            if len(positions) < 10:
                continue

            # Calculate variance in x and y separately
            x_coords = [p[0] for p in positions]
            y_coords = [p[1] for p in positions]

            if len(x_coords) > 1:
                x_var = statistics.variance(x_coords)
                y_var = statistics.variance(y_coords)
                total_var = (x_var + y_var) ** 0.5  # RMS variance
                variances.append(total_var)

        if variances:
            print(f"Objects tracked >10 frames: {len(variances)}")
            print(f"Average position variance:  {statistics.mean(variances):.1f}px")
            print(f"Median position variance:   {statistics.median(variances):.1f}px")
        else:
            print("Not enough data (no objects tracked >10 frames)")

    def _analyze_detection_vs_tracking(self):
        """Compare raw detections vs tracked output"""
        print("DETECTION vs TRACKING")
        print("-" * 60)

        raw_counts = [f['raw_count'] for f in self.frames]
        tracked_counts = [f['tracked_count'] for f in self.frames]

        avg_raw = statistics.mean(raw_counts) if raw_counts else 0
        avg_tracked = statistics.mean(tracked_counts) if tracked_counts else 0

        print(f"Average raw detections:     {avg_raw:.1f} objects/frame")
        print(f"Average tracked detections: {avg_tracked:.1f} objects/frame")
        print(f"Reduction:                  {avg_raw - avg_tracked:.1f} ({100*(avg_raw-avg_tracked)/avg_raw:.1f}%)")

        # Frame-by-frame consistency
        variance_raw = statistics.variance(raw_counts) if len(raw_counts) > 1 else 0
        variance_tracked = statistics.variance(tracked_counts) if len(tracked_counts) > 1 else 0

        print(f"\nFrame-to-frame variance:")
        print(f"  Raw:                      {variance_raw:.2f}")
        print(f"  Tracked:                  {variance_tracked:.2f}")
        print(f"  Improvement:              {100*(variance_raw-variance_tracked)/variance_raw:.1f}%")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_detections.py <log_file_or_dir>")
        sys.exit(1)

    path = Path(sys.argv[1])

    # If directory, find latest log
    if path.is_dir():
        logs = sorted(path.glob("detections_*.jsonl"))
        if not logs:
            print(f"No detection logs found in {path}")
            sys.exit(1)
        log_file = logs[-1]
        print(f"Using latest log: {log_file.name}")
    else:
        log_file = path

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        sys.exit(1)

    # Run analysis
    analyzer = DetectionAnalyzer(log_file)
    analyzer.analyze()


if __name__ == "__main__":
    main()
