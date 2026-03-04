# https://pysource.com
import numpy as np
import pyrealsense2 as rs

from aaa_core.config.console import error, status, success, warning


class RealsenseCamera:
    def __init__(self):
        # Configure depth and color streams
        status("Loading Intel Realsense Camera")

        self.pipeline = rs.pipeline()

        config = rs.config()
        # RGB: 1080p for better segmentation detail
        rgb_width, rgb_height, rgb_fps = 1920, 1080, 30
        config.enable_stream(
            rs.stream.color, rgb_width, rgb_height, rs.format.bgr8, rgb_fps
        )
        status(f"  RGB configured: {rgb_width}×{rgb_height} @ {rgb_fps} FPS")

        # Depth: 848x480 @ 30 FPS (Intel's optimal depth resolution, safe framerate)
        # Note: 90 FPS causes "failed to set power state" error
        depth_width, depth_height, depth_fps = 848, 480, 30
        config.enable_stream(
            rs.stream.depth, depth_width, depth_height, rs.format.z16, depth_fps
        )
        status(f"  Depth configured: {depth_width}×{depth_height} @ {depth_fps} FPS")

        # Start streaming
        status("Starting RealSense pipeline...")
        profile = self.pipeline.start(config)
        status("✓ RealSense pipeline started successfully")

        # Store profile for later use
        self.profile = profile

        # Report device info from the active pipeline (avoids creating a
        # separate rs.context whose background device-watcher thread can
        # race with the pipeline and segfault on macOS/libusb)
        self._report_device_info(profile)

        # Verify actual stream configurations
        for stream_profile in profile.get_streams():
            stream_type = stream_profile.stream_type()
            if stream_type == rs.stream.color:
                video_profile = stream_profile.as_video_stream_profile()
                actual_w = video_profile.width()
                actual_h = video_profile.height()
                actual_fps = video_profile.fps()
                status(f"  RGB actual: {actual_w}×{actual_h} @ {actual_fps} FPS")
            elif stream_type == rs.stream.depth:
                video_profile = stream_profile.as_video_stream_profile()
                actual_w = video_profile.width()
                actual_h = video_profile.height()
                actual_fps = video_profile.fps()
                status(f"  Depth actual: {actual_w}×{actual_h} @ {actual_fps} FPS")

        # Wait a moment for camera to stabilize after start
        import time

        time.sleep(0.5)

        # Configure RGB sensor to reduce noise (optional - camera works without this)
        try:
            device = profile.get_device()

            rgb_sensor = None
            for sensor in device.query_sensors():
                if sensor.is_color_sensor():
                    rgb_sensor = sensor
                    break

            if rgb_sensor:
                # Enable auto-exposure for dynamic lighting adaptation
                try:
                    rgb_sensor.set_option(rs.option.enable_auto_exposure, 1)
                    status("✓ RealSense: Auto-exposure enabled")
                except Exception as e:
                    status(f"  RealSense: Could not enable auto exposure ({e})")

                # Enable auto white balance for color accuracy
                try:
                    rgb_sensor.set_option(rs.option.enable_auto_white_balance, 1)
                    status("✓ RealSense: Auto white balance enabled")
                except Exception as e:
                    status(f"  RealSense: Could not enable auto white balance ({e})")

                # Uncomment below for manual exposure control (disable auto-exposure):
                # try:
                #     rgb_sensor.set_option(rs.option.enable_auto_exposure, 0)
                #     rgb_sensor.set_option(rs.option.exposure, 1200)  # Fixed exposure value
                #     status("✓ RealSense: Fixed exposure enabled")
                # except Exception as e:
                #     status(f"  RealSense: Could not set fixed exposure ({e})")
                #
                # Uncomment below for manual white balance (disable auto-WB):
                # try:
                #     rgb_sensor.set_option(rs.option.enable_auto_white_balance, 0)
                #     rgb_sensor.set_option(rs.option.white_balance, 4600)
                #     status("✓ RealSense: Fixed white balance enabled")
                # except Exception as e:
                #     status(f"  RealSense: Could not set fixed white balance ({e})")

                # Set power line frequency to reduce fluorescent light flicker
                # 1 = 50Hz (Europe), 2 = 60Hz (North America)
                try:
                    rgb_sensor.set_option(rs.option.power_line_frequency, 2)  # 60Hz
                    status("✓ RealSense: Power line frequency set to 60Hz")
                except Exception as e:
                    status(f"  RealSense: Could not set power line frequency ({e})")
        except Exception as e:
            status(f"  RealSense: Sensor configuration skipped ({e})")

        # Align color TO depth so both share the 848x480 depth grid.
        # This produces a pixel-aligned color+depth pair for point cloud generation
        # without upscaling depth (preserves native depth resolution).
        # The 1920x1080 RGB feed is still returned separately for video display.
        self.align = rs.align(rs.stream.depth)

        # Align depth TO color so display depth shares the 1920x1080 color FOV.
        # This eliminates the zoom mismatch when toggling between RGB and depth views
        # (depth sensor has wider FOV: 86x57 deg vs color's 69x42 deg).
        self.align_to_color = rs.align(rs.stream.color)

    def get_frame_stream(self):
        """
        Capture a coherent set of frames from RealSense.

        Returns:
            Tuple of (success, color_1080p, depth_480p, aligned_color_480p, display_depth_1080p)
            - color_1080p: BGR uint8 (1080, 1920, 3) for video display
            - depth_480p: uint16 (480, 848) native depth in mm
            - aligned_color_480p: BGR uint8 (480, 848, 3) pixel-aligned to depth
            - display_depth_1080p: uint16 (1080, 1920) depth aligned to color FOV for display
        """
        try:
            # Use longer timeout (10 seconds) to handle exposure adjustments
            frames = self.pipeline.wait_for_frames(timeout_ms=10000)

            # Get native color frame (1920x1080) for video display
            color_frame = frames.get_color_frame()
            # Get native depth frame (848x480)
            depth_frame = frames.get_depth_frame()

            if not depth_frame or not color_frame:
                error(
                    "Impossible to get the frame, make sure that the Intel "
                    "Realsense camera is correctly connected"
                )
                return False, None, None, None, None

            # Produce aligned color (848x480) that shares the depth grid
            aligned_color_frame = None
            if self.align:
                aligned_frames = self.align.process(frames)
                aligned_color_frame = aligned_frames.get_color_frame()

            # Produce display depth (1920x1080) aligned to color camera FOV
            display_depth_frame = None
            if self.align_to_color:
                color_aligned_frames = self.align_to_color.process(frames)
                display_depth_frame = color_aligned_frames.get_depth_frame()

        except RuntimeError as e:
            # Timeout or other runtime error
            error(f"RealSense frame timeout: {e}")
            return False, None, None, None, None

        # Apply filter to fill the Holes in the depth image
        spatial = rs.spatial_filter()
        spatial.set_option(rs.option.holes_fill, 3)
        filtered_depth = spatial.process(depth_frame)

        hole_filling = rs.hole_filling_filter()
        filled_depth = hole_filling.process(filtered_depth)

        # Apply same filters to display depth for visual quality
        display_depth_image = None
        if display_depth_frame:
            display_spatial = rs.spatial_filter()
            display_spatial.set_option(rs.option.holes_fill, 3)
            filtered_display = display_spatial.process(display_depth_frame)
            display_hole_filling = rs.hole_filling_filter()
            filled_display = display_hole_filling.process(filtered_display)
            display_depth_image = np.asanyarray(filled_display.get_data())

        # Convert images to numpy arrays
        depth_image = np.asanyarray(filled_depth.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        aligned_color_image = None
        if aligned_color_frame:
            aligned_color_image = np.asanyarray(aligned_color_frame.get_data())

        return True, color_image, depth_image, aligned_color_image, display_depth_image

    def set_exposure(self, exposure_value: int) -> bool:
        """
        Set camera exposure value

        Args:
            exposure_value: Exposure value (typically 50-300)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the device from pipeline
            profile = self.pipeline.get_active_profile()
            device = profile.get_device()

            # Find RGB sensor
            for sensor in device.query_sensors():
                if sensor.is_color_sensor():
                    # Set exposure
                    sensor.set_option(rs.option.exposure, exposure_value)
                    status(f"✓ RealSense exposure set to {exposure_value}")

                    # Give camera time to adjust (prevent frame timeout)
                    import time

                    return True

            error("RGB sensor not found")
            return False
        except Exception as e:
            error(f"Failed to set exposure: {e}")
            return False

    def _report_device_info(self, profile):
        """Report RealSense device info from the active pipeline profile.

        Uses the already-running pipeline's device rather than creating a
        separate rs.context(), which avoids a race condition between the
        context's background device-watcher thread and libusb on macOS
        that causes a segfault (SIGSEGV in pthread_mutex_lock).
        """
        try:
            dev = profile.get_device()
            name = dev.get_info(rs.camera_info.name)
            serial = dev.get_info(rs.camera_info.serial_number)
            firmware = dev.get_info(rs.camera_info.firmware_version)

            # Get USB type - critical for performance
            try:
                usb_type = dev.get_info(rs.camera_info.usb_type_descriptor)
            except Exception:
                usb_type = "unknown"

            # Use print() directly to ensure output in daemon context
            print(f"  Device: {name}")
            print(f"  Serial: {serial}")
            print(f"  Firmware: {firmware}")

            # Report USB type with warning if USB 2.x
            if usb_type.startswith("2"):
                print(f"  ⚠ USB Type: {usb_type} (USB 2.0 - LIMITED PERFORMANCE!)")
                print("  ⚠ Tip: Unplug and replug cable with quick, firm insertion")
                print("  ⚠ See docs/realsense-setup.md for cable troubleshooting")
            else:
                print(f"  ✓ USB Type: {usb_type} (USB 3.0 - Good)")

        except Exception as e:
            status(f"  Could not query device info: {e}")

    def release(self):
        self.pipeline.stop()
        # print(depth_image)

        # Apply colormap on depth image
        # (image must be converted to 8-bit per pixel first)
        # depth_colormap = cv2.applyColorMap(
        #     cv2.convertScaleAbs(depth_image, alpha=0.10), 2
        # )

        # Stack both images horizontally
        # images = np.hstack((color_image, depth_colormap))
