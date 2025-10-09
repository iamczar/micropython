import utime as time

class PID:
    def __init__(self, Kp, Ki, Kd, setpoint=0, output_limits=(None, None)):
        """Initialize a custom PID controller."""
        self.Kp = Kp  # Proportional gain
        self.Ki = Ki  # Integral gain
        self.Kd = Kd  # Derivative gain
        self.setpoint = setpoint  # Desired value to achieve

        # Output limits to prevent integral windup and excessive output
        self.output_limits = output_limits
        self.min_output, self.max_output = output_limits

        # Internal state
        self._previous_error = 0
        self._integral = 0
        self._last_output = 0
        self._last_time = time.ticks_ms()  # Start with the current system time

    def compute(self, measured_value):
        """Compute the PID output given a measured value."""
        current_time = time.ticks_ms()
        time_delta = current_time - self._last_time  # Calculate time since last update

        if time_delta > 0:  # Proceed only if time has passed
            # Convert milliseconds to seconds for proper scaling
            time_delta_sec = time_delta / 1000.0
            
            # Calculate error
            error = self.setpoint - measured_value

            # Proportional term
            proportional = self.Kp * error

            # Integral term with proper time scaling (no anti-windup guard)
            self._integral += self.Ki * error * time_delta_sec
            
            # Derivative term with proper time scaling
            derivative = (error - self._previous_error) / time_delta_sec if time_delta_sec > 0 else 0
            derivative_term = self.Kd * derivative

            # Compute PID output
            output = proportional + self._integral + derivative_term
            output = self._clamp(output)  # Apply output limits

            # Store previous state
            self._previous_error = error
            self._last_time = current_time
            self._last_output = output

            return output

        # If no computation is done, return the last output
        return self._last_output

    def set_output_limits(self, min_output, max_output):
        """Set limits for the PID output."""
        self.min_output = min_output
        self.max_output = max_output

    def set_setpoint(self, setpoint):
        """Update the desired setpoint."""
        self.setpoint = setpoint
        
    def set_kp(self, Kp):
        """Dynamically set the proportional gain."""
        self.Kp = Kp

    def set_ki(self, Ki):
        """Dynamically set the integral gain."""
        self.Ki = Ki

    def set_kd(self, Kd):
        """Dynamically set the derivative gain."""
        self.Kd = Kd

    def reset(self):
        """Reset the PID controller internals."""
        self._previous_error = 0
        self._integral = 0
        self._last_output = 0
        self._last_time = time.ticks_ms()  # Reset time

    def _clamp(self, value):
        """Clamp the value to the specified output limits."""
        if self.min_output is not None and value < self.min_output:
            return self.min_output
        elif self.max_output is not None and value > self.max_output:
            return self.max_output
        return value
