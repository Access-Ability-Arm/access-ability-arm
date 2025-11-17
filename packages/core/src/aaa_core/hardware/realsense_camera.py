# https://pysource.com
import numpy as np
import pyrealsense2 as rs

from aaa_core.config.console import error, status


class RealsenseCamera:
    def __init__(self):
        # Configure depth and color streams
        status("Loading Intel Realsense Camera")
        self.pipeline = rs.pipeline()

        config = rs.config()
        # RGB: 1080p for better segmentation detail
        rgb_width, rgb_height, rgb_fps = 1920, 1080, 30
        config.enable_stream(rs.stream.color, rgb_width, rgb_height, rs.format.bgr8, rgb_fps)
        status(f"  RGB configured: {rgb_width}×{rgb_height} @ {rgb_fps} FPS")

        # Depth: 848x480 @ 30 FPS (Intel's optimal depth resolution, safe framerate)
        # Note: 90 FPS causes "failed to set power state" error
        depth_width, depth_height, depth_fps = 848, 480, 30
        config.enable_stream(rs.stream.depth, depth_width, depth_height, rs.format.z16, depth_fps)
        status(f"  Depth configured: {depth_width}×{depth_height} @ {depth_fps} FPS")

        # Start streaming
        status("Starting RealSense pipeline...")
        profile = self.pipeline.start(config)
        status("✓ RealSense pipeline started successfully")

        # Store profile for later use
        self.profile = profile

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

        # Alignment disabled - RGB is 1920x1080, depth is 848x480 (native resolutions)
        # This saves bandwidth and processing power. Depth won't be pixel-aligned with RGB,
        # but for object segmentation we don't need perfect alignment.
        # To re-enable alignment (upscales depth to match RGB resolution):
        # align_to = rs.stream.color
        # self.align = rs.align(align_to)
        self.align = None

    def get_frame_stream(self):
        # Wait for a coherent pair of frames: depth and color
        try:
            # Use longer timeout (10 seconds) to handle exposure adjustments
            frames = self.pipeline.wait_for_frames(timeout_ms=10000)

            # Apply alignment if enabled (upscales depth to match RGB)
            if self.align:
                aligned_frames = self.align.process(frames)
                depth_frame = aligned_frames.get_depth_frame()
                color_frame = aligned_frames.get_color_frame()
            else:
                # No alignment - use native resolutions
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()

            if not depth_frame or not color_frame:
                # If there is no frame, probably camera not connected
                error(
                    "Impossible to get the frame, make sure that the Intel "
                    "Realsense camera is correctly connected"
                )
                return False, None, None
        except RuntimeError as e:
            # Timeout or other runtime error
            error(f"RealSense frame timeout: {e}")
            return False, None, None

        # Apply filter to fill the Holes in the depth image
        spatial = rs.spatial_filter()
        spatial.set_option(rs.option.holes_fill, 3)
        filtered_depth = spatial.process(depth_frame)

        hole_filling = rs.hole_filling_filter()
        filled_depth = hole_filling.process(filtered_depth)

        # Create colormap to show the depth of the Objects
        colorizer = rs.colorizer()
        depth_colormap = np.asanyarray(  # noqa: F841
            colorizer.colorize(filled_depth).get_data()
        )

        # Convert images to numpy arrays
        # distance = depth_frame.get_distance(int(50),int(50))
        # print("distance", distance)
        depth_image = np.asanyarray(filled_depth.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        # cv2.imshow("Colormap", depth_colormap)
        # cv2.imshow("depth img", depth_image)

        return True, color_image, depth_image

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
                    time.sleep(0.3)
                    return True

            error("RGB sensor not found")
            return False
        except Exception as e:
            error(f"Failed to set exposure: {e}")
            return False

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
