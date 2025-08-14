import uasyncio as asyncio
import uos
import gc
import time
import json
from event_bus import EventBus
from pyb import USB_VCP
from simple_logger import SimpleLogger

# State Pattern Implementation
class State:
    """Base state class for the state machine"""
    
    def __init__(self, context):
        self.context = context
        self.logger = context.logger
    
    async def enter(self):
        """Called when entering this state"""
        pass
    
    async def exit(self):
        """Called when exiting this state"""
        pass
    
    async def handle_message(self, message):
        """Handle incoming message in this state"""
        pass
    
    async def update(self):
        """Called every loop iteration in this state"""
        pass
    
    def get_name(self):
        """Return state name"""
        return self.__class__.__name__

class IdleState(State):
    """Idle state - waiting for commands"""
    
    def __init__(self, context):
        super().__init__(context)
        self.last_idle_message_time = 0
    
    async def enter(self):
        await self.context._send_state_notification("idle", {
            "action": "entered_idle",
            "description": "Ready for commands"
        })
        self.last_idle_message_time = 0  # Reset timer
    
    async def update(self):
        """Send periodic idle messages to show we're alive and ready"""
        import utime
        current_time = utime.time() * 1000  # Convert to milliseconds
        
        # Send idle message every 5 seconds
        if current_time - self.last_idle_message_time > 5000:  # 5 seconds
            await self.context._send_state_notification("idle", {
                "action": "idle_heartbeat",
                "description": "Ready for commands",
                "timestamp": current_time
            })
            self.last_idle_message_time = current_time
    
    async def handle_message(self, message):
        # Parse and route commands
        try:
            message_data = json.loads(message)
            inner_message = message_data.get("message", {})
            command = inner_message.get("command")
            
            if command == "sequence_cmd":
                await self.context._transition_to_state("waiting_for_sequence")
                await self.context.states["waiting_for_sequence"].handle_message(message)
            elif command in ["stop", "pause", "resume", "start_data_log", "stop_data_log", "retrieve_data"]:
                await self.context.handle_command(json.dumps(inner_message), command)
            else:
                self.logger.warning(f"AlphaCommsManager: Unknown command in idle state: {command}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling message in idle state: {e}")

class WaitingForSequenceState(State):
    """Waiting for sequence initialization"""
    
    async def enter(self):
        await self.context._send_state_notification("waiting_for_sequence", {
            "action": "waiting_for_sequence_init",
            "description": "Waiting for sequence initialization"
        })
    
    async def handle_message(self, message):
        try:
            message_data = json.loads(message)
            inner_message = message_data.get("message", {})
            command = inner_message.get("command")
            
            if command == "sequence_cmd":
                # Check if this is an init command
                command_data = json.loads(json.dumps(inner_message))
                if "number_of_states" in command_data:
                    # Handle sequence initialization
                    await self._handle_sequence_init(command_data)
                else:
                    self.logger.warning("AlphaCommsManager: Received sequence command but not init")
            else:
                self.logger.warning(f"AlphaCommsManager: Unexpected command in waiting state: {command}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling message in waiting state: {e}")
    
    async def _handle_sequence_init(self, command_data):
        """Handle sequence initialization"""
        try:
            number_of_states = command_data.get("number_of_states", 0)
            
            self.logger.info(f"AlphaCommsManager: Received sequence init, states: {number_of_states}")
            
            # Clear existing sequence file
            self.context.clear_sequence_file()
            
            # Store sequence info
            self.context.sequence_total_states = number_of_states
            self.context.sequence_current_state = 0
            self.context.sequence_retry_count = 0
            self.context.last_sequence_request_time = 0
            
            # Transition to receiving state
            await self.context._transition_to_state("receiving_sequence", {
                "action": "starting_sequence_reception",
                "total_states": number_of_states
            })
            
            # Send acknowledgment
            ack_response = {
                "command": "sequence_ack",
                "sequence_ack": "init",
                "status": "ready"
            }
            await self.context.send_status(ack_response)
            
            # Note: Sequence request will be sent by ReceivingSequenceState.update() method
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling sequence init: {e}")
            await self.context._transition_to_state("error", {
                "error": "sequence_init_failed",
                "details": str(e)
            })

class ReceivingSequenceState(State):
    """Receiving sequence data"""
    
    def __init__(self, context):
        super().__init__(context)
        self.transition_attempted = False  # Prevent infinite transition attempts
    
    async def enter(self):
        self.transition_attempted = False  # Reset on entry
        await self.context._send_state_notification("receiving_sequence", {
            "action": "started_receiving_sequence",
            "description": "Receiving sequence data"
        })
    
    async def update(self):
        """Check for retry timeouts, send sequence requests, and check for completion"""
        if self.context._check_sequence_retry_timeout():
            await self.context._transition_to_state("error")
        elif self.context.sequence_current_state >= self.context.sequence_total_states and not self.transition_attempted:
            # Sequence is complete, transition to completed state (only attempt once)
            self.transition_attempted = True
            self.logger.info(f"AlphaCommsManager: Update method - sequence complete! Transitioning to completed state (current: {self.context.sequence_current_state}, total: {self.context.sequence_total_states})")
            try:
                await self.context._transition_to_state("completed")
                self.logger.info(f"AlphaCommsManager: Successfully transitioned to completed state")
            except Exception as e:
                self.logger.error(f"AlphaCommsManager: Failed to transition to completed state: {e}")
                # Fallback: try to transition directly
                try:
                    self.context.current_state = "completed"
                    self.context.current_state_object = self.context.states["completed"]
                    await self.context.current_state_object.enter()
                    self.logger.info(f"AlphaCommsManager: Fallback transition to completed state successful")
                except Exception as fallback_e:
                    self.logger.error(f"AlphaCommsManager: Fallback transition also failed: {fallback_e}")
        elif self.context.sequence_retry_count >= 0 and self.context.sequence_current_state < self.context.sequence_total_states:
            # Request next line if not complete
            self.logger.info(f"AlphaCommsManager: Update method - requesting line {self.context.sequence_current_state} (current: {self.context.sequence_current_state}, total: {self.context.sequence_total_states})")
            await self.context._request_sequence_line_with_retry(self.context.sequence_current_state)
        else:
            self.logger.info(f"AlphaCommsManager: Update method - not requesting (retry_count: {self.context.sequence_retry_count}, current: {self.context.sequence_current_state}, total: {self.context.sequence_total_states})")
    
    async def handle_message(self, message):
        try:
            message_data = json.loads(message)
            inner_message = message_data.get("message", {})
            command = inner_message.get("command")
            
            if command == "sequence_cmd":
                command_data = json.loads(json.dumps(inner_message))
                
                if "sequence_number" in command_data:
                    # Sequence line data
                    await self._handle_sequence_line(inner_message)
                elif "number_of_states" in command_data:
                    # Re-initialization
                    await self.context._transition_to_state("waiting_for_sequence")
                    await self.context.states["waiting_for_sequence"].handle_message(message)
                else:
                    self.logger.warning("AlphaCommsManager: Unknown sequence command format")
            else:
                self.logger.warning(f"AlphaCommsManager: Unexpected command in receiving state: {command}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling message in receiving state: {e}")
    
    async def _handle_sequence_line(self, command):
        """Handle individual sequence line"""
        try:
            # Removed forced garbage collection to reduce overhead
            
            # command is already the inner message part, not the full JSON
            command_data = command if isinstance(command, dict) else json.loads(command)
            sequence_number = command_data.get("sequence_number")
            state_data = command_data.get("state", {})
            
            self.logger.info(f"AlphaCommsManager: Received sequence state {sequence_number}")
            
            if not isinstance(state_data, dict):
                self.logger.error(f"AlphaCommsManager: Invalid state data format")
                return
            
            if self.context.save_json_sequence_line(sequence_number, state_data):
                self.logger.info(f"AlphaCommsManager: Saved JSON sequence line {sequence_number}")
                
                # Reset retry counter
                self.context._reset_sequence_retry()
                
                # Send acknowledgment
                ack_response = {
                    "command": "sequence_ack",
                    "sequence_ack": sequence_number,
                    "status": "received"
                }
                await self.context.send_status(ack_response)
                
                # Move to next state
                self.context.sequence_current_state += 1
                
                # Send progress notification
                await self.context._send_state_notification("receiving_sequence", {
                    "action": "sequence_progress",
                    "progress": f"{self.context.sequence_current_state}/{self.context.sequence_total_states}",
                    "percentage": (self.context.sequence_current_state / self.context.sequence_total_states) * 100
                })
                
                # Note: Completion check is now handled in the update() method
                # This ensures the state machine progresses even without new messages
                    
            else:
                self.logger.error(f"AlphaCommsManager: Failed to save JSON sequence line {sequence_number}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling sequence line: {e}")

class CompletedState(State):
    """Sequence completed successfully"""
    
    async def enter(self):
        await self.context._complete_sequence()
        # Automatically transition to idle after a short delay
        await asyncio.sleep(0.5)  # 500ms delay
        await self.context._transition_to_state("idle")
    
    async def handle_message(self, message):
        try:
            message_data = json.loads(message)
            inner_message = message_data.get("message", {})
            command = inner_message.get("command")
            
            if command == "stop":
                # Reset to idle on stop command
                await self.context._transition_to_state("idle")
            else:
                self.logger.info(f"AlphaCommsManager: Ignoring command in completed state: {command}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling message in completed state: {e}")

class ErrorState(State):
    """Error state - sequence failed"""
    
    async def enter(self):
        await self.context._send_state_notification("error", {
            "action": "entered_error_state",
            "description": "Sequence processing failed"
        })
    
    async def handle_message(self, message):
        try:
            message_data = json.loads(message)
            inner_message = message_data.get("message", {})
            command = inner_message.get("command")
            
            if command == "stop":
                # Reset to idle on stop command
                await self.context._transition_to_state("idle")
            else:
                self.logger.info(f"AlphaCommsManager: Ignoring command in error state: {command}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling message in error state: {e}")

class AlphaCommsManager:
    # State machine states
    STATE_IDLE = "idle"
    STATE_WAITING_FOR_SEQUENCE = "waiting_for_sequence"
    STATE_RECEIVING_SEQUENCE = "receiving_sequence"
    STATE_COMPLETED = "completed"
    STATE_ERROR = "error"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_MS = 1000  # 1 second between retries
    
    def __init__(self, usb_vcp: USB_VCP, 
                 event_bus: EventBus = None, 
                 logger: SimpleLogger = None,
                 module_id: str = "3000"):
        """
        Initialize the AlphaCommsManager.
        
        Args:
            usb_vcp: USB_VCP communication interface (used for receiving commands only)
            event_bus: EventBus instance for publishing events
            logger: Logger instance for debugging (required) - used for sending all outgoing messages
            module_id: Module identifier for data logging
        """
        if logger is None:
            raise ValueError("Logger is required for AlphaCommsManager")
        
        self.usb_vcp = usb_vcp
        self.event_bus = event_bus
        self.logger = logger
        self.module_id = module_id
        self._is_connected = True
        
        # State machine properties
        self.current_state = self.STATE_IDLE
        self.sequence_total_states = 0
        self.sequence_current_state = 0
        self.sequence_retry_count = 0
        self.last_sequence_request_time = 0
        
        # JSONL file management
        self.jsonl_file_path = "/sd/sequences/current_sequence.json"
        self.jsonl_data_lines = 0
        self.max_jsonl_lines = 1000  # Configurable limit
        
        # Communication state
        self._connection_check_interval = 1.0  # seconds
        
        # Initialize file system
        self._init_file_system()
        
        # Initialize states
        self.states = {
            "idle": IdleState(self),
            "waiting_for_sequence": WaitingForSequenceState(self),
            "receiving_sequence": ReceivingSequenceState(self),
            "completed": CompletedState(self),
            "error": ErrorState(self)
        }
        self.current_state_object = self.states["idle"]
        
        # Initialize state object
        asyncio.create_task(self.current_state_object.enter())
    
    def _init_file_system(self):
        """Initialize file system and create necessary directories"""
        try:
            # Create sequences directory if it doesn't exist
            try:
                uos.mkdir("/sd/sequences")
            except OSError:
                # Directory already exists
                pass
            
            # Clear any existing sequence file
            self._clear_current_sequence_file()
            
            self.logger.info("AlphaCommsManager: File system initialized")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: File system init error: {e}")
    
    def _clear_current_sequence_file(self):
        """Clear the current sequence file"""
        try:
            with open(self.jsonl_file_path, "w") as f:
                f.write("")  # Clear file - no header needed for JSONL format
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error clearing sequence file: {e}")
       
    def check_connection(self) -> bool:
        """
        Check if USB_VCP is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._is_connected
    
    def _update_connection_status(self):
        """Update connection status by checking USB_VCP"""
        try:
            was_connected = self._is_connected
            self._is_connected = self.usb_vcp.isconnected()
            
            # Handle connection state changes
            if was_connected and not self._is_connected:
                self.logger.warning("AlphaCommsManager: USB_VCP disconnected")
            elif not was_connected and self._is_connected:
                self.logger.info("AlphaCommsManager: USB_VCP reconnected")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error checking connection: {e}")
            self._is_connected = False
    
    def _read_line(self) -> str:
        """
        Read a complete line from USB_VCP.
        
        Returns:
            str: Line content or None if no data
        """
        if not self.check_connection():
            return None
            
        max_buffer_size = 2000  # Increased for large JSON messages
        buffer = b""
        
        try:
            while self.usb_vcp.any():
                char = self.usb_vcp.read(1)
                if char == b"\n" or len(buffer) >= max_buffer_size:
                    break
                buffer += char
            
            return buffer.decode("utf-8").strip() if buffer else None
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error reading from USB_VCP: {e}")
            return None
    
    def _flush_serial_buffer(self):
        """Flush the serial buffer"""
        try:
            while self.usb_vcp.any():
                self.usb_vcp.read()
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error flushing serial buffer: {e}")
    
    def save_json_sequence_line(self, sequence_number: int, data: dict) -> bool:
        """
        Save sequence line as JSONL (JSON Lines) format to sequence file.
        Each line is a complete JSON object, allowing efficient appending.
        
        Args:
            sequence_number: Sequence line number
            data: Sequence data as dictionary (already in JSON format from Proteus)
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            # Create JSON object for this sequence line
            sequence_line = {
                "sequence_number": sequence_number,
                "data": data,
                "timestamp": self.logger.get_timestamp()
            }
            
            # Append as a single JSON line to the file
            with open(self.jsonl_file_path, "a") as f:
                f.write(json.dumps(sequence_line) + "\n")
            
            # Track line count
            self.jsonl_data_lines += 1
                
            # Check if we've exceeded the limit
            if self.jsonl_data_lines > self.max_jsonl_lines:
                self.logger.warning(f"AlphaCommsManager: JSONL sequence line limit exceeded ({self.max_jsonl_lines})")
                return False
            
            self.logger.info(f"AlphaCommsManager: Appended JSONL sequence line {sequence_number} to file")
            return True
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error saving JSONL sequence line: {e}")
            return False
    
    async def send_status(self, status):
        """
        Send status message to Proteus via SimpleLogger.
        
        Args:
            status: Status message as dictionary or JSON string
        """
        if not self.check_connection():
            self.logger.info("AlphaCommsManager: No connection, skipping status send")
            return
        
        try:
            self.logger.info(f"AlphaCommsManager: Sending status: {status}")
            # Handle both dictionary and JSON string inputs
            if isinstance(status, dict):
                # Direct dictionary - send via system message
                self.logger.info("AlphaCommsManager: Sending dictionary status")
                self.logger.send_system_message("alpha_comms_manager", status)
                self.logger.info("AlphaCommsManager: Dictionary status sent")
            elif isinstance(status, str):
                # JSON string - parse and send
                if status.startswith('{') and status.endswith('}'):
                    try:
                        status_data = json.loads(status)
                        self.logger.send_system_message("alpha_comms_manager", status_data)
                    except json.JSONDecodeError:
                        # Log error for invalid JSON
                        self.logger.error("AlphaCommsManager: Invalid JSON in status message")
                else:
                    # For non-JSON messages, just log them
                    self.logger.info(f"AlphaCommsManager: Non-JSON status: {status}")
            else:
                self.logger.error("AlphaCommsManager: Invalid status type")
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error sending status: {e}")
            self.logger.error(f"AlphaCommsManager: Exception type: {type(e)}")
    
    def handle_usb_disconnect(self):
        """Handle USB disconnection"""
        self._is_connected = False
        self.logger.warning("AlphaCommsManager: USB_VCP disconnected")
    
    def handle_usb_reconnect(self):
        """Handle USB reconnection"""
        self._is_connected = True
        self.logger.info("AlphaCommsManager: USB_VCP reconnected")
       
    def get_jsonl_file_path(self) -> str:
        """Get the current JSONL file path"""
        return self.jsonl_file_path
    
    def count_jsonl_lines(self) -> int:
        """
        Count the actual number of valid JSON lines in the file.
        More accurate than the tracked count.
        """
        try:
            count = 0
            try:
                with open(self.jsonl_file_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                if "sequence_number" in data and "data" in data:
                                    count += 1
                            except json.JSONDecodeError:
                                continue  # Skip invalid lines
            except OSError:
                # File doesn't exist yet
                pass
            return count
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error counting JSONL lines: {e}")
            return 0
    
    def clear_sequence_file(self):
        """Clear the sequence file"""
        self._clear_current_sequence_file()
        
        self.logger.info("AlphaCommsManager: Cleared sequence file")
    
    async def _send_state_notification(self, state: str, details: dict = None):
        """
        Send a state notification to the host.
        
        Args:
            state: Current state
            details: Optional details about the state
        """
        notification = {
            "command": "state_notification",
            "state": state,
            "sequence_current": self.sequence_current_state,
            "sequence_total": self.sequence_total_states
        }
        
        if details:
            notification.update(details)
            
        self.logger.send_system_message("alpha_comms_manager", notification)
        self.logger.info(f"AlphaCommsManager: State changed to {state}")
    
    async def _transition_to_state(self, new_state: str, details: dict = None):
        """
        Transition to a new state and send notification.
        
        Args:
            new_state: New state to transition to
            details: Optional details about the state change
        """
        old_state = self.current_state
        old_state_object = self.current_state_object
        
        if old_state != new_state:
            # Exit old state
            if old_state_object:
                try:
                    await old_state_object.exit()
                except Exception as e:
                    self.logger.error(f"AlphaCommsManager: Error exiting old state {old_state}: {e}")
            
            # Update current state
            self.current_state = new_state
            self.current_state_object = self.states[new_state]
            
            # Enter new state
            try:
                await self.current_state_object.enter()
            except Exception as e:
                self.logger.error(f"AlphaCommsManager: Error entering new state {new_state}: {e}")
                raise  # Re-raise to let caller handle it
            
            # Send notification
            try:
                await self._send_state_notification(new_state, details)
            except Exception as e:
                self.logger.error(f"AlphaCommsManager: Error sending state notification: {e}")
    
    async def communication_loop(self):
        """
        Main communication loop for USB_VCP.
        Handles incoming messages and maintains connection status.
        """
        while True:
            try:
                # Update connection status
                self._update_connection_status()
                
                # Handle state-specific logic
                await self.current_state_object.update()
                
                # Read incoming messages
                if self.check_connection():
                    message = self.receive_message()
                    if message:
                        await self.current_state_object.handle_message(message)
                
                await asyncio.sleep(0.1)  # 100ms delay
                
            except Exception as e:
                self.logger.error(f"AlphaCommsManager: Error in communication loop: {e}")
                await asyncio.sleep(1.0)  # Longer delay on error
    
    def receive_message(self) -> str:
        """
        Receive a message from Proteus.
        
        Returns:
            str: Message content or None if no data
        """
        try:
            line = self._read_line()
            if line is None:
                return None
            
            self.logger.info(f"AlphaCommsManager: Received message: {line}")
            
            return line
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error receiving message: {e}")
            return None
    
    async def _request_sequence_line_with_retry(self, line_number: int):
        """
        Request a specific sequence line from Proteus with retry logic.
        
        Args:
            line_number: Line number to request
        """
        try:
            import utime
            current_time = utime.time() * 1000  # Convert to milliseconds
            
            # Check if we should retry
            if self.sequence_retry_count > 0:
                # Ensure last_sequence_request_time is a number
                last_time = float(self.last_sequence_request_time) if isinstance(self.last_sequence_request_time, str) else self.last_sequence_request_time
                time_since_last_request = current_time - last_time
                if time_since_last_request < self.RETRY_DELAY_MS:
                    # Not enough time has passed, skip this retry
                    return
            
            self.logger.info(f"AlphaCommsManager: Requesting sequence line {line_number} (attempt {self.sequence_retry_count + 1}/{self.MAX_RETRIES})")
            
            request = {
                "command": "sequence_request",
                "sequence_request": line_number
            }
            
            # Send directly via SimpleLogger to reduce call stack depth
            self.logger.send_system_message("alpha_comms_manager", request)
            
            self.last_sequence_request_time = current_time
            self.sequence_retry_count += 1
            
            self.logger.info(f"AlphaCommsManager: Sent sequence request for line {line_number}")
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error requesting sequence line: {e}")
            self.logger.error(f"AlphaCommsManager: Exception type: {type(e)}")
            self.logger.error(f"AlphaCommsManager: Exception details: {str(e)}")
    
    def _reset_sequence_retry(self):
        """Reset the retry counter when a sequence line is received"""
        self.sequence_retry_count = 0
        self.last_sequence_request_time = 0
    
    async def _complete_sequence(self):
        """
        Complete the sequence and send completion notification.
        """
        try:
            # Count actual lines in file
            total_sequences = self.count_jsonl_lines()
            
            self.logger.info(f"AlphaCommsManager: Sequence complete. Total sequences: {total_sequences}")
            
            # Send completion message
            completion_response = {
                "command": "sequence_complete",
                "total_sequences": total_sequences,
                "file_path": self.jsonl_file_path,
                "status": "completed"
            }
            
            await self.send_status(completion_response)
            
            # Reset retry counters
            self._reset_sequence_retry()
            
            # Publish completion event if event bus is available
            if self.event_bus:
                await self.event_bus.publish("sequence-complete", {
                    "file_path": self.jsonl_file_path,
                    "total_sequences": total_sequences
                })
                
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error completing sequence: {e}")
            await self._transition_to_state(self.STATE_ERROR, {
                "error": "sequence_completion_failed",
                "details": str(e)
            })
    
    async def handle_command(self, command: str, command_type: str):
        """
        Generic command handler for all command types.
        
        Args:
            command: The command string
            command_type: Type of command (stop, pause, resume, etc.)
        """
        try:
            self.logger.info(f"AlphaCommsManager: Received {command_type.upper()} command")
            
            # Reset state machine for stop command
            if command_type == "stop" and self.current_state != self.STATE_IDLE:
                await self._reset_state_machine()
            
            # Send acknowledgment
            ack_response = {
                "command": command_type,
                "status": "acknowledged"
            }
            await self.send_status(ack_response)
            
            self.logger.info(f"AlphaCommsManager: {command_type.upper()} command acknowledged")
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error handling {command_type} command: {e}")
    
    async def handle_stop_command(self, command: str):
        """Handle stop command"""
        await self.handle_command(command, "stop")
    
    async def handle_pause_command(self, command: str):
        """Handle pause command"""
        await self.handle_command(command, "pause")
    
    async def handle_resume_command(self, command: str):
        """Handle resume command"""
        await self.handle_command(command, "resume")
    
    async def handle_start_data_log_command(self, command: str):
        """Handle start data log command"""
        await self.handle_command(command, "start_data_log")
    
    async def handle_stop_data_log_command(self, command: str):
        """Handle stop data log command"""
        await self.handle_command(command, "stop_data_log")
    
    async def handle_retrieve_data_command(self, command: str):
        """Handle retrieve data command"""
        await self.handle_command(command, "retrieve_data")
    
    def _check_sequence_retry_timeout(self):
        """
        Check if we've exceeded max retries for sequence requests.
        Returns True if we should send a failure message.
        """
        if self.sequence_retry_count >= self.MAX_RETRIES:
            self.logger.error(f"AlphaCommsManager: Max retries ({self.MAX_RETRIES}) exceeded for sequence line {self.sequence_current_state}")
            return True
        return False
    
    async def _send_sequence_failure_message(self):
        """
        Send a sequence failure message and transition to error state.
        """
        try:
            failure_message = {
                "command": "sequence_failure",
                "failed_line": self.sequence_current_state,
                "total_states": self.sequence_total_states,
                "status": "failed_to_receive"
            }
            
            self.logger.send_system_message("alpha_comms_manager", failure_message)
            self.logger.error(f"AlphaCommsManager: Sent sequence failure message for line {self.sequence_current_state}")
            
            # Transition to error state
            await self._transition_to_state(self.STATE_ERROR, {
                "error": "sequence_failure",
                "failed_line": self.sequence_current_state,
                "total_states": self.sequence_total_states
            })
            
            # Reset retry counters
            self._reset_sequence_retry()
            
        except Exception as e:
            self.logger.error(f"AlphaCommsManager: Error sending failure message: {e}")
            await self._transition_to_state(self.STATE_ERROR, {
                "error": "failure_message_error",
                "details": str(e)
            }) 

    async def _reset_state_machine(self):
        """
        Reset the state machine to idle state.
        """
        self.sequence_current_state = 0
        self.sequence_total_states = 0
        self._reset_sequence_retry()
        await self._transition_to_state("idle", {
            "action": "state_machine_reset"
        }) 