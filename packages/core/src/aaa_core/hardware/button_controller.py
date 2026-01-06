"""
Button Controller for Robotic Arm
Monitors button press duration to differentiate between press and hold actions
"""

import threading
import time


class ButtonController(threading.Thread):
    """
    Thread that monitors button press duration
    Differentiates between quick press (<0.5s) and hold (>0.5s)
    """

    def __init__(self, hold_threshold: float = 0.5):
        """
        Initialize button controller

        Args:
            hold_threshold: Time in seconds to distinguish press from hold
        """
        super(ButtonController, self).__init__(daemon=True)
        print("Button controller initialized")
        self.hold_threshold = hold_threshold
        self.current_state = None
        self.start_time = 0
        self.elapsed_time = 0
        self.button_pushed = False

    def run(self):
        """Monitor button state while pressed"""
        while self.current_state == "pressed":
            self.elapsed_time = time.time() - self.start_time

            if self.button_pushed and self.elapsed_time > self.hold_threshold:
                print("Button is being held")
                self.button_pushed = False

            time.sleep(0.1)

    def update_button_state(
        self, current_state: str, start_time: float, button_name: str
    ):
        """
        Update the current button state

        Args:
            current_state: 'pressed' or 'released'
            start_time: Time when button was pressed
            button_name: Name of the button (e.g., 'x', 'y', 'z', 'grip')
        """
        self.current_state = current_state

        if self.current_state == "pressed":
            self.start_time = start_time
            self.button_pushed = True

        elif self.current_state == "released":
            if self.elapsed_time < self.hold_threshold:
                print(f"{button_name} was pressed")
                self.button_pushed = False
            else:
                print(f"{button_name} held for {self.elapsed_time:.2f} seconds")

    def stop(self):
        """Stop the button controller thread"""
        self.current_state = None  # This will cause run() to exit
        # Thread is daemon so it will exit when main thread exits
        # But we can also try to join with timeout
        if self.is_alive():
            self.join(timeout=1.0)
