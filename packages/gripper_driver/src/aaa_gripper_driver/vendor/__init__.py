"""
Vendored third-party libraries for AAA Gripper Driver

This directory contains the scservo_sdk from Waveshare's STServo Python SDK.
"""

# Import from the vendored scservo_sdk
try:
    from .scservo_sdk import PortHandler, scscl, COMM_SUCCESS
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    PortHandler = None
    scscl = None
    COMM_SUCCESS = None

__all__ = ["PortHandler", "scscl", "COMM_SUCCESS", "SDK_AVAILABLE"]
