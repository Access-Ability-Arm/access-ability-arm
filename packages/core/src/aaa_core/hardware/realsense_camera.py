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
        config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)

        # Start streaming
        profile = self.pipeline.start(config)

        # Store profile for later use
        self.profile = profile

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
                # Disable autoexposure for consistent quality (prevents flickering)
                # Fixed exposure reduces noise from fluorescent lighting
                try:
                    rgb_sensor.set_option(rs.option.enable_auto_exposure, 0)
                    # Set fixed exposure (adjust based on lighting - range typically 1-10000)
                    # Lower = darker but less noise, Higher = brighter but more noise
                    rgb_sensor.set_option(rs.option.exposure, 250)  # Default: 250 (brighter)
                    status("✓ RealSense: Fixed exposure enabled (reduces fluorescent light noise)")
                except Exception as e:
                    status(f"  RealSense: Using auto exposure ({e})")

                # Disable auto white balance for color consistency
                try:
                    rgb_sensor.set_option(rs.option.enable_auto_white_balance, 0)
                    # Set fixed white balance (range: 2800-6500, default: 4600)
                    rgb_sensor.set_option(rs.option.white_balance, 4600)
                    status("✓ RealSense: Fixed white balance enabled")
                except Exception as e:
                    status(f"  RealSense: Using auto white balance ({e})")

                # Set power line frequency to reduce fluorescent light flicker
                # 1 = 50Hz (Europe), 2 = 60Hz (North America)
                try:
                    rgb_sensor.set_option(rs.option.power_line_frequency, 2)  # 60Hz
                    status("✓ RealSense: Power line frequency set to 60Hz")
                except Exception as e:
                    status(f"  RealSense: Could not set power line frequency ({e})")
        except Exception as e:
            status(f"  RealSense: Sensor configuration skipped ({e})")

        align_to = rs.stream.color
        self.align = rs.align(align_to)

    def get_frame_stream(self):
        # Wait for a coherent pair of frames: depth and color
        frames = self.pipeline.wait_for_frames()
        aligned_frames = self.align.process(frames)
        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()

        if not depth_frame or not color_frame:
            # If there is no frame, probably camera not connected
            error(
                "Impossible to get the frame, make sure that the Intel "
                "Realsense camera is correctly connected"
            )
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
