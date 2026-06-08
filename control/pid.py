import time

class PIDController:

    def __init__(self, kp, ki, kd):

        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.previous_error = 0
        self.integral = 0
        self._last_t = time.time()          # Bug 1 fixed

    def compute(self, error):

        now = time.time()
        dt = now - self._last_t
        dt = max(dt, 1e-4)                  # prevent division by zero

        # Proportional
        p = self.kp * error

        # Integral
        self.integral += error * dt
        i = self.ki * self.integral         # Bug 2 fixed

        # Derivative
        derivative = (error - self.previous_error) / dt  # Bug 3 fixed
        d = self.kd * derivative

        # Save state
        self.previous_error = error
        self._last_t = now                  # Bug 4 fixed

        # Final output
        output = p + i + d

        return output