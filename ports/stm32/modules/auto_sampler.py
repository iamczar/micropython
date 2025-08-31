import pyb
import uasyncio as asyncio
from event_bus import EventBus
import time


class AutoSamplerCmd:
    """Command constants for AutoSampler"""
    STOP = 0
    RESET = 1
    RUN = 2
    
    _cmd_map = {
        STOP: "STOP",
        RESET: "RESET",
        RUN: "RUN",
    }

    @classmethod
    def to_string(cls, value):
        return cls._cmd_map.get(value, "Unknown")


class AutoSamplerSensorState:
    """Sensor state constants"""
    bottom = 0
    home = 1
    top = 2
    unknown = -1
    
    _sensor_state_map = {
        bottom: "bottom",
        home: "home",
        top: "top",
        unknown: "unknown",
    }

    @classmethod
    def to_string(cls, value):
        return cls._sensor_state_map.get(value, "Unknown")


class AutoSamplerActuatorCmds:
    """Actuator command constants"""
    go_up = 0
    go_down = 1
    stop = 2
    
    _actuator_cmd_map = {
        go_up: "go_up",
        go_down: "go_down",
        stop: "stop",
    }

    @classmethod
    def to_string(cls, value):
        return cls._actuator_cmd_map.get(value, "Unknown")


# State Pattern Implementation
class AutoSamplerState:
    """Base state class for AutoSampler state machine"""
    
    def __init__(self, context):
        self.context = context
        self.logger = context.logger
    
    async def enter(self):
        """Called when entering this state"""
        if self.logger:
            self.logger.info(f"Sampler {self.context.sampler_id}: Entering {self.get_name()}")
    
    async def exit(self):
        """Called when exiting this state"""
        if self.logger:
            self.logger.debug(f"Sampler {self.context.sampler_id}: Exiting {self.get_name()}")
    
    async def update(self):
        """Called every loop iteration in this state"""
        pass
    
    async def handle_command(self, cmd, data):
        """Handle incoming command in this state"""
        pass
    
    def get_name(self):
        """Return state name"""
        return self.__class__.__name__
    
    def check_timeout(self):
        """Check if current operation has timed out"""
        if hasattr(self, 'start_time') and self.start_time:
            return time.time() - self.start_time > self.context.timeout_threshold
        return False


class PowerOnState(AutoSamplerState):
    """Initial power-on state"""
    
    async def enter(self):
        await super().enter()
        # Immediately transition to waiting for command
        await self.context.transition_to_state("waiting_for_command")


class WaitingForCommandState(AutoSamplerState):
    """Waiting for commands from external sources"""
    
    async def enter(self):
        await super().enter()
        # Stop any movement and reset command
        self.context.stop()
        self.context.current_cmd = AutoSamplerCmd.STOP
        self.last_status_time = 0
        await self.context.publish_status("waiting_for_command", "Ready for commands")
    
    async def update(self):
        # Periodic heartbeat so host can observe idle readiness
        now = time.time()
        if now - self.last_status_time >= 1:
            self.last_status_time = now
            await self.context.publish_status("waiting_for_command", "Ready for commands")

    async def handle_command(self, cmd, data):
        """Process commands received while waiting"""
        self.context.current_cmd = cmd
        
        if cmd == AutoSamplerCmd.STOP:
            # Move to explicit stopped state which requires RESET to continue
            await self.context.transition_to_state("stopped")
            
        elif cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")
            
        elif cmd == AutoSamplerCmd.RUN:
            # Store hold time and check position
            self.context.hold_time_secs = data.get('hold_time', 0) * 3600  # Convert hours to seconds
            if self.context.current_sensor_state == AutoSamplerSensorState.home:
                await self.context.transition_to_state("moving_to_bottom_run")
            else:
                await self.context.publish_error("Not at home position for RUN, need RESET first")
                
        # DELAYED_RUN removed
            
        else:
            self.logger.warning(f"Sampler {self.context.sampler_id}: Unknown command {cmd}")


# DelayedRunWaitingState removed (feature deprecated)


class MovingToBottomResetState(AutoSamplerState):
    """Moving to bottom position for reset operation"""
    
    async def enter(self):
        await super().enter()
        self.start_time = time.time()
        self.context.go_down()
        self.last_status_time = 0
        await self.context.publish_status("moving_to_bottom", "Moving to bottom for reset")
    
    async def update(self):
        """Check if reached bottom position"""
        # Periodic movement heartbeat including current sensor state
        now = time.time()
        if now - getattr(self, 'last_status_time', 0) >= 1:
            self.last_status_time = now
            await self.context.publish_status("moving_to_bottom", "Moving to bottom for reset")
        if self.context.current_sensor_state == AutoSamplerSensorState.bottom:
            self.context.stop()
            await self.context.publish_status("moving_to_bottom", "bottom reached")
            await self.context.transition_to_state("moving_to_home")
        elif self.check_timeout():
            await self.context.transition_to_state("error")
    
    async def handle_command(self, cmd, data):
        """Only STOP command allowed during movement"""
        if cmd == AutoSamplerCmd.STOP:
            await self.context.transition_to_state("stopped")


class MovingToBottomRunState(AutoSamplerState):
    """Moving to bottom position for run operation"""
    
    async def enter(self):
        await super().enter()
        self.start_time = time.time()
        self.context.go_down()
        self.last_status_time = 0
        await self.context.publish_status("moving_to_bottom", "Moving to bottom for sampling")
    
    async def update(self):
        """Check if reached bottom position"""
        # Periodic movement heartbeat including current sensor state
        now = time.time()
        if now - getattr(self, 'last_status_time', 0) >= 1:
            self.last_status_time = now
            await self.context.publish_status("moving_to_bottom", "Moving to bottom for sampling")
        if self.context.current_sensor_state == AutoSamplerSensorState.bottom:
            self.context.stop()
            await self.context.transition_to_state("holding_position")
        elif self.check_timeout():
            await self.context.transition_to_state("error")
    
    async def handle_command(self, cmd, data):
        """Only STOP and RESET allowed during movement"""
        if cmd == AutoSamplerCmd.STOP:
            await self.context.transition_to_state("stopped")
        elif cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")


class HoldingPositionState(AutoSamplerState):
    """Holding at bottom position for sampling"""
    
    async def enter(self):
        await super().enter()
        self.start_time = time.time()
        hold_hours = self.context.hold_time_secs / 3600
        self.logger.info(f"Sampler {self.context.sampler_id}: Holding for {hold_hours}h at bottom")
        self.last_log_time = 0
        await self.context.publish_status("holding_position", f"Sampling for {hold_hours}h")
    
    async def update(self):
        """Check if hold time has elapsed"""
        elapsed_time = time.time() - self.start_time
        # Emit remaining time every second
        remaining = max(0, self.context.hold_time_secs - elapsed_time)
        if int(elapsed_time) - getattr(self, 'last_log_time', 0) >= 1:
            self.last_log_time = int(elapsed_time)
            await self.context.publish_status("holding_position", f"{remaining:.1f}s remaining")
        if elapsed_time >= self.context.hold_time_secs:
            self.logger.info(f"Sampler {self.context.sampler_id}: Hold complete, moving to top")
            await self.context.transition_to_state("moving_to_top")
    
    async def handle_command(self, cmd, data):
        """Handle commands during hold (STOP and RESET allowed)"""
        if cmd == AutoSamplerCmd.STOP:
            await self.context.transition_to_state("stopped")
        elif cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")


class MovingToHomeState(AutoSamplerState):
    """Moving to home position"""
    
    async def enter(self):
        await super().enter()
        self.start_time = time.time()
        self.context.go_up()
        self.last_status_time = 0
        await self.context.publish_status("moving_to_home", "Moving to home position")
    
    async def update(self):
        """Check if reached home position"""
        # Periodic movement heartbeat including current sensor state
        now = time.time()
        if now - getattr(self, 'last_status_time', 0) >= 1:
            self.last_status_time = now
            await self.context.publish_status("moving_to_home", "Moving to home position")
        if self.context.current_sensor_state == AutoSamplerSensorState.home:
            self.context.stop()
            await self.context.transition_to_state("waiting_for_command")
        elif self.check_timeout():
            await self.context.transition_to_state("error")
    
    async def handle_command(self, cmd, data):
        """Only STOP allowed during movement"""
        if cmd == AutoSamplerCmd.STOP:
            await self.context.transition_to_state("stopped")


class MovingToTopState(AutoSamplerState):
    """Moving to top position for extraction"""
    
    async def enter(self):
        await super().enter()
        self.start_time = time.time()
        self.context.go_up()
        self.top_detection_count = 0
        self.last_status_time = 0
        await self.context.publish_status("moving_to_top", "Moving to top for extraction")
    
    async def update(self):
        """Check if reached top position"""
        # Periodic movement heartbeat including current sensor state
        now = time.time()
        if now - getattr(self, 'last_status_time', 0) >= 1:
            self.last_status_time = now
            await self.context.publish_status("moving_to_top", "Moving to top for extraction")
        if self.context.current_sensor_state == AutoSamplerSensorState.top:
            self.top_detection_count += 1
            # Need consistent detection to avoid false positives
            if self.top_detection_count >= 2:
                self.context.stop()
                await self.context.transition_to_state("extraction_complete")
        else:
            self.top_detection_count = 0
            
        if self.check_timeout():
            await self.context.transition_to_state("error")
    
    async def handle_command(self, cmd, data):
        """Only STOP and RESET allowed during movement"""
        if cmd == AutoSamplerCmd.STOP:
            await self.context.transition_to_state("stopped")
        elif cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")


class StoppedState(AutoSamplerState):
    """Explicit stopped state that requires RESET to leave."""

    async def enter(self):
        await super().enter()
        self.context.stop()
        self.last_status_time = 0
        await self.context.publish_status("stopped", "Stopped - RESET required to continue")

    async def update(self):
        # Heartbeat so host can observe persistent stopped state
        now = time.time()
        if now - self.last_status_time >= 1:
            self.last_status_time = now
            await self.context.publish_status("stopped", "Stopped - RESET required to continue")

    async def handle_command(self, cmd, data):
        if cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")
        elif cmd == AutoSamplerCmd.STOP:
            # Already stopped; refresh status
            await self.context.publish_status("stopped", "Stopped - RESET required to continue")
        else:
            await self.context.publish_error("Command not allowed while stopped - send RESET")


class ExtractionCompleteState(AutoSamplerState):
    """State entered after reaching the top completing extraction. Requires RESET to proceed."""

    async def enter(self):
        await super().enter()
        self.context.stop()
        self.last_status_time = 0
        await self.context.publish_status("extraction_complete", "Sample extraction complete - RESET required")

    async def update(self):
        # Heartbeat to indicate completion persists until RESET
        now = time.time()
        if now - self.last_status_time >= 1:
            self.last_status_time = now
            await self.context.publish_status("extraction_complete", "Sample complete - RESET required")

    async def handle_command(self, cmd, data):
        if cmd == AutoSamplerCmd.RESET:
            await self.context.transition_to_state("moving_to_bottom_reset")
        elif cmd == AutoSamplerCmd.STOP:
            # STOP keeps it in completion state
            await self.context.publish_status("extraction_complete", "Sample complete - RESET required")
        else:
            await self.context.publish_error("Command not allowed after extraction - send RESET")


class ErrorState(AutoSamplerState):
    """Error state for handling timeouts and failures"""
    
    async def enter(self):
        await super().enter()
        self.context.stop()  # Stop all movement
        self.last_status_time = 0
        await self.context.publish_error("AutoSampler entered error state - timeout or failure")
        self.logger.error(f"Sampler {self.context.sampler_id}: Entered error state")
    
    async def update(self):
        # Periodically emit error state heartbeat so host can observe persistent errors
        now = time.time()
        if now - self.last_status_time >= 2:  # every 2 seconds
            self.last_status_time = now
            await self.context.publish_status("error", "In error state - awaiting RESET")

    async def handle_command(self, cmd, data):
        """Only RESET command can exit error state"""
        if cmd == AutoSamplerCmd.RESET:
            self.logger.info(f"Sampler {self.context.sampler_id}: RESET command received, exiting error state")
            await self.context.transition_to_state("moving_to_bottom_reset")
        else:
            self.logger.warning(f"Sampler {self.context.sampler_id}: Only RESET allowed in error state")


class AutoSamplerV2:
    """
    State-based AutoSampler implementation using the State Pattern.
    Each state is a separate class that handles its own behavior and transitions.
    """
    
    def __init__(self, sampler_id, limit_switch_pin_1, limit_switch_pin_2, 
                 out_1_pin, out_2_pin, event_bus: EventBus,
                 command_topic=None, logger=None, sensor_loop_hz=1):
        
        # Basic configuration
        self.sampler_id = sampler_id
        self.event_bus = event_bus
        self.logger = logger
        # Errors and status are emitted via logger system messages; no error topic
        self.check_interval = 1 / sensor_loop_hz
        self.loop_is_running = True
        
        # Hardware configuration
        self.limit_switch_1 = pyb.Pin(limit_switch_pin_1, pyb.Pin.IN)
        self.limit_switch_2 = pyb.Pin(limit_switch_pin_2, pyb.Pin.IN)
        self.out_1 = pyb.Pin(out_1_pin, pyb.Pin.OUT_PP)
        self.out_2 = pyb.Pin(out_2_pin, pyb.Pin.OUT_PP)
        
        # State management
        self.current_sensor_state = AutoSamplerSensorState.unknown
        self.current_cmd = AutoSamplerCmd.STOP
        self.timeout_threshold = 90  # seconds
        
        # Operation parameters
        self.hold_time_secs = 0
        # delayed run removed
        
        # Initialize states
        self.states = {
            "power_on": PowerOnState(self),
            "waiting_for_command": WaitingForCommandState(self),
            "moving_to_bottom_reset": MovingToBottomResetState(self),
            "moving_to_bottom_run": MovingToBottomRunState(self),
            "holding_position": HoldingPositionState(self),
            "moving_to_home": MovingToHomeState(self),
            "moving_to_top": MovingToTopState(self),
            "stopped": StoppedState(self),
            "extraction_complete": ExtractionCompleteState(self),
            "error": ErrorState(self),
        }
        
        self.current_state = self.states["power_on"]
        
        # Subscribe to command events
        self.command_topic = command_topic or f"auto-s-cmds-{self.sampler_id}"
        self.event_bus.subscribe(self.command_topic, self.handle_cmd_event)
        
        if self.logger:
            self.logger.info(f"AutoSamplerV2 {self.sampler_id} initialized on topic: {self.command_topic}")

    def get_sensor_state(self):
        """Determine current state from sensor inputs"""
        pin_state = (self.limit_switch_1.value(), self.limit_switch_2.value())
        state_lookup = {
            (0, 0): AutoSamplerSensorState.bottom,
            (1, 0): AutoSamplerSensorState.home,
            (0, 1): AutoSamplerSensorState.top
        }
        return state_lookup.get(pin_state, AutoSamplerSensorState.unknown)

    def go_up(self):
        """Activate motor to go up"""
        self.out_1.low()
        self.out_2.high()

    def go_down(self):
        """Activate motor to go down"""
        self.out_1.high()
        self.out_2.low()

    def stop(self):
        """Stop the motor"""
        self.out_1.high()
        self.out_2.high()

    async def transition_to_state(self, state_name):
        """Transition to a new state"""
        if state_name not in self.states:
            self.logger.error(f"Sampler {self.sampler_id}: Unknown state: {state_name}")
            return
        
        try:
            # Exit current state
            await self.current_state.exit()
            
            # Switch to new state
            old_state = self.current_state.get_name()
            self.current_state = self.states[state_name]
            
            # Enter new state
            await self.current_state.enter()
            
            if self.logger:
                self.logger.debug(f"Sampler {self.sampler_id}: {old_state} -> {self.current_state.get_name()}")
                
        except Exception as e:
            self.logger.error(f"Sampler {self.sampler_id}: Error transitioning to {state_name}: {e}")
            # Try to go to error state
            self.current_state = self.states["error"]
            await self.current_state.enter()

    async def publish_status(self, status, description):
        """Publish status message via system message logger"""
        try:
            message = {
                "sampler_id": self.sampler_id,
                "status": status,
                "description": description,
                "state": self.current_state.get_name(),
                "sensor_state": AutoSamplerSensorState.to_string(self.current_sensor_state),
                "timestamp": time.time()
            }
            if self.logger:
                # Send structured system message for host-side consumption
                self.logger.send_system_message("auto_sampler", message)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Sampler {self.sampler_id}: Error publishing status: {e}")

    async def publish_error(self, error_message):
        """Publish error message via system message logger"""
        try:
            payload = {
                "event": "error",
                "sampler_id": self.sampler_id,
                "details": error_message,
                "state": self.current_state.get_name(),
                "sensor_state": AutoSamplerSensorState.to_string(self.current_sensor_state),
                "timestamp": time.time()
            }
            if self.logger:
                self.logger.send_system_message("auto_sampler", payload)
                self.logger.error(f"Sampler {self.sampler_id}: {error_message}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Sampler {self.sampler_id}: Error publishing error: {e}")

    async def handle_cmd_event(self, data):
        """Handle commands from event bus (async)"""
        try:
            # Handle both AutoSamplerCmds objects and dictionaries
            if hasattr(data, 'cmd'):
                # AutoSamplerCmds object
                cmd = data.cmd
                cmd_data = {
                    'hold_time': getattr(data, 'hold_time_hrs', 0),
                    'delay_seconds': getattr(data, 'delay_seconds', 0)
                }
            else:
                # Dictionary format
                cmd = data.get("cmd")
                cmd_data = {
                    'hold_time': data.get("hold_time", 0),
                    'delay_seconds': data.get("delay_seconds", 0)
                }
            
            # Store command for async processing by main loop
            self.pending_command = (cmd, cmd_data)
            
            if self.logger:
                self.logger.info(f"Sampler {self.sampler_id}: Queued command {AutoSamplerCmd.to_string(cmd)}")

            # Publish a system status message that a command was received
            try:
                await self.publish_status(
                    "command_received",
                    f"Queued {AutoSamplerCmd.to_string(cmd)} (hold={cmd_data.get('hold_time', 0)}h, delay={cmd_data.get('delay_seconds', 0)}s)"
                )
            except Exception:
                # Non-fatal if status publish fails
                pass
        except Exception as e:
            if self.logger:
                self.logger.error(f"Sampler {self.sampler_id}: Error handling command: {e}")

    async def process_pending_command(self):
        """Process any pending commands (called from main loop)"""
        if hasattr(self, 'pending_command'):
            cmd, cmd_data = self.pending_command
            delattr(self, 'pending_command')
            await self.current_state.handle_command(cmd, cmd_data)

    async def loop(self):
        """Main loop for the AutoSampler"""
        # Ensure initial state's enter() runs so we emit initial status
        if not hasattr(self, "_entered") or not self._entered:
            try:
                await self.current_state.enter()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Sampler {self.sampler_id}: Error on initial enter: {e}")
            self._entered = True

        while self.loop_is_running:
            try:
                # Update sensor state
                self.current_sensor_state = self.get_sensor_state()
                
                # Process any pending commands
                await self.process_pending_command()
                
                # Update current state
                await self.current_state.update()
                
            except Exception as e:
                self.logger.error(f"Sampler {self.sampler_id}: Error in main loop: {e}")
                # Try to go to error state
                await self.transition_to_state("error")
            
            await asyncio.sleep(self.check_interval)

    async def stop_test(self):
        """Stop the sampler (for testing purposes)"""
        self.loop_is_running = False
        self.stop()
        if self.logger:
            self.logger.info(f"AutoSamplerV2 {self.sampler_id} stopped")
