"""
SequenceController - Manages sequence execution from JSONL files

This controller reads sequence data from current_sequence.json and executes
each sequence line in order, maintaining persistent state of current position.
"""

import uasyncio as asyncio
import uos
import json
import time
from simple_logger import SimpleLogger
from event_bus import EventBus
from command_data_structure import (
    OxyPumpCmds, PressurePumpCmds, ValveAndAirPumpCmds,
)

class SequenceState:
    """Enumeration of sequence controller states"""
    IDLE = "idle"
    LOADING = "loading"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

class SequenceController:
    """
    Sequence Controller with State Machine
    
    Manages the execution of sequence files with persistent state tracking.
    """
    
    def __init__(self, event_bus: EventBus = None, logger: SimpleLogger = None):
        """
        Initialize the SequenceController.
        
        Args:
            event_bus: EventBus instance for publishing events
            logger: Logger instance for debugging
        """
        self.event_bus = event_bus
        self.logger = logger or SimpleLogger("SequenceController")
        
        # File paths
        self.sequence_file_path = "/sd/sequences/current_sequence.json"
        self.state_file_path = "/sd/sequences/current_sequence_number.txt"
        
        # State machine
        self.current_state = SequenceState.IDLE
        self.sequence_data = []
        self.current_sequence_number = 0
        self.total_sequences = 0
        
        # Execution control
        self.is_running = False
        self.execution_delay = 1.0  # seconds between sequence lines
        
        # Heartbeat/status publishing
        self.status_interval = 1.0  # seconds between status heartbeats
        self._status_task = None
        
        # Initialize file system
        self._init_file_system()
        
        # Subscribe to events
        if self.event_bus:
            self._subscribe_to_events()
        
        # Start status heartbeat so host can always see controller state
        self._start_status_heartbeat()

    def _publish_zero_commands(self):
        """Publish zeroed commands to put actuators in a safe state."""
        try:
            # Oxy pump zero
            oxy_cmd = OxyPumpCmds()
            oxy_cmd.circFlowSpeed = 0
            oxy_cmd.oxySP = 0.0
            oxy_cmd.oxyKp = 0.0
            oxy_cmd.oxyKi = 0.0
            oxy_cmd.oxyKd = 0.0
            oxy_cmd.pump1dir = 0
            oxy_cmd.tube_bore = 1
            oxy_cmd.pump_2_speed_ratio = 0.0

            # Pressure pump zero
            pres_cmd = PressurePumpCmds()
            pres_cmd.pressureFlowSpeed = 0
            pres_cmd.pressureSP = 0.0
            pres_cmd.pressureKp = 0.0
            pres_cmd.pressureKi = 0.0
            pres_cmd.pressureKd = 0.0
            pres_cmd.pump2dir = 0
            pres_cmd.tube_bore = 1

            # Valves and air pumps zero (all off)
            va_cmd = ValveAndAirPumpCmds()
            for idx in range(1, 10 + 1):
                va_cmd.set_valve_air_pump(idx, 0)
            va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump1, 0)
            va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump2, 0)

            # Wrist zero
            wrist_cmd = 0

            if self.event_bus:
                import uasyncio as asyncio
                asyncio.create_task(self.event_bus.publish("oxy-pump-cmds", oxy_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("pressure-pump-cmd", pres_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("valve-airpump-cmds", va_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("wrist-cmds", wrist_cmd))
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Error publishing zero commands: {e}")
            except Exception:
                pass

    def _start_status_heartbeat(self):
        """Ensure the periodic status heartbeat task is running."""
        try:
            if self._status_task is None:
                self._status_task = asyncio.create_task(self._status_heartbeat_loop())
                self.logger.info("SequenceController: Status heartbeat started")
        except Exception as e:
            # On environments without a running loop yet, starter may fail; it's okay
            self.logger.warning(f"SequenceController: Failed to start status heartbeat: {e}")

    async def _status_heartbeat_loop(self):
        """Publish a periodic status message for host visibility."""
        while True:
            try:
                status = {
                    "event": "status",
                    "state": self.current_state,
                    "current_sequence": int(self.current_sequence_number),
                    "total_sequences": int(self.total_sequences),
                    "is_running": bool(self.is_running),
                    "progress": f"{self.current_sequence_number}/{self.total_sequences}" if self.total_sequences > 0 else "0/0",
                }
                # System message for structured host-side consumption
                try:
                    self.logger.send_system_message("sequence_controller", status)
                except Exception:
                    pass
                # Note: No event bus publish for status to reduce on-device chatter
            except Exception:
                # Keep heartbeat alive regardless of transient errors
                pass
            await asyncio.sleep(self.status_interval)
    
    def _init_file_system(self):
        """Initialize file system and create necessary directories"""
        try:
            # Create sequences directory if it doesn't exist
            try:
                uos.mkdir("/sd/sequences")
            except OSError:
                # Directory already exists
                pass
            
            self.logger.info("SequenceController: File system initialized")
                
        except Exception as e:
            self.logger.error(f"SequenceController: File system init error: {e}")
    
    def _subscribe_to_events(self):
        """Subscribe to relevant event bus topics"""
        if self.event_bus:
            self.event_bus.subscribe("sequence-complete", self.handle_sequence_complete)
            self.event_bus.subscribe("stop-cmd", self.handle_stop_command)
            self.event_bus.subscribe("pause-cmd", self.handle_pause_command)
            self.event_bus.subscribe("resume-cmd", self.handle_resume_command)
            
            self.logger.info("SequenceController: Subscribed to event bus topics")
    
    def _save_current_sequence_number(self):
        """Save current sequence number to persistent storage"""
        try:
            with open(self.state_file_path, "w") as f:
                f.write(str(self.current_sequence_number))
            self.logger.info(f"SequenceController: Saved sequence number {self.current_sequence_number}")
        except Exception as e:
            self.logger.error(f"SequenceController: Error saving sequence number: {e}")
    
    def _load_current_sequence_number(self):
        """Load current sequence number from persistent storage"""
        try:
            with open(self.state_file_path, "r") as f:
                content = f.read().strip()
                if content:
                    self.current_sequence_number = int(content)
                    self.logger.info(f"SequenceController: Loaded sequence number {self.current_sequence_number}")
                else:
                    self.current_sequence_number = 0
        except (OSError, ValueError):
            # File doesn't exist or invalid content
            self.current_sequence_number = 0
            self.logger.info("SequenceController: Starting from sequence number 0")
    
    def _load_sequence_file(self) -> bool:
        """
        Load sequence data from JSONL file.
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            self.sequence_data = []
            try:
                with open(self.sequence_file_path, "r") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                # Accept either {sequence_number, data} or {sequence_number, state}
                                if "sequence_number" in data and ("data" in data or "state" in data):
                                    if "state" in data and "data" not in data:
                                        # Normalize to {sequence_number, data}
                                        data = {"sequence_number": data["sequence_number"], "data": data["state"]}
                                    self.sequence_data.append(data)
                                else:
                                    self.logger.warning(f"SequenceController: Invalid JSONL line {line_num}: missing required fields")
                            except json.JSONDecodeError as e:
                                self.logger.warning(f"SequenceController: Invalid JSON at line {line_num}: {e}")
                                continue
            except OSError:
                self.logger.error("SequenceController: Sequence file not found")
                return False
            
            self.total_sequences = len(self.sequence_data)
            self.logger.info(f"SequenceController: Loaded {self.total_sequences} sequence lines")
            return True
            
        except Exception as e:
            self.logger.error(f"SequenceController: Error loading sequence file: {e}")
            return False
    
    def _execute_sequence_line(self, sequence_data: dict) -> bool:
        """
        Execute a single sequence line.
        
        Args:
            sequence_data: Sequence data dictionary
            
        Returns:
            bool: True if executed successfully, False otherwise
        """
        try:
            sequence_number = sequence_data.get("sequence_number")
            data = sequence_data.get("data", {})
            
            self.logger.info(f"SequenceController: Executing sequence {sequence_number}")
            # Emit a lightweight system message for host-side verification
            try:
                self.logger.send_system_message("sequence_controller", {
                    "event": "executing",
                    "sequence": int(sequence_number),
                    "total_sequences": int(self.total_sequences)
                })
            except Exception:
                pass
            
            # Map JSON data to command structures used system-wide
            
            # Oxy pump commands
            oxy_cmd = OxyPumpCmds()
            oxy_cmd.circFlowSpeed = int(data.get("circFlow", 0))
            oxy_cmd.oxySP = float(data.get("oxySP", 0.0))
            oxy_cmd.oxyKp = float(data.get("oxyKp", 0.0))
            oxy_cmd.oxyKi = float(data.get("oxyKi", 0.0))
            oxy_cmd.oxyKd = float(data.get("oxyKd", 0.0))
            oxy_cmd.pump1dir = 1 if data.get("pump1Dir", True) else 0
            oxy_cmd.tube_bore = int(data.get("tube_bore", 1))
            oxy_cmd.pump_2_speed_ratio = float(data.get("pump_2_speed_ratio", 1.0))
            
            # Pressure pump commands
            pres_cmd = PressurePumpCmds()
            pres_cmd.pressureFlowSpeed = int(data.get("pressureFlow", 0))
            pres_cmd.pressureSP = float(data.get("pressureSP", 0.0))
            pres_cmd.pressureKp = float(data.get("pressureKp", 0.0))
            pres_cmd.pressureKi = float(data.get("pressureKi", 0.0))
            pres_cmd.pressureKd = float(data.get("pressureKd", 0.0))
            pres_cmd.pump2dir = 1 if data.get("pump2Dir", True) else 0
            pres_cmd.tube_bore = int(data.get("tube_bore", 1))
            
            # Valve and air pump bitfield
            va_cmd = ValveAndAirPumpCmds()
            for idx in range(1, 11):
                key = f"valve{idx}"
                if key in data:
                    va_cmd.set_valve_air_pump(idx, 1 if data.get(key) else 0)
            # air pumps indices 11 and 12
            if "airpump1" in data:
                va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump1, 1 if data.get("airpump1") else 0)
            if "airpump2" in data:
                va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump2, 1 if data.get("airpump2") else 0)
            
            # Wrist command
            wrist_cmd = int(data.get("wristCmd", 0))
            
            # Publish packed commands to topics (mirroring SerialCommandParser)
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("oxy-pump-cmds", oxy_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("pressure-pump-cmd", pres_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("valve-airpump-cmds", va_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("wrist-cmds", wrist_cmd))
                asyncio.create_task(self.event_bus.publish("data-log-cmd", True))
                # Note: AutoSampler commands intentionally not handled here
            
            self.logger.info(f"SequenceController: Dispatched sequence {sequence_number} commands")
            try:
                self.logger.send_system_message("sequence_controller", {
                    "event": "dispatched",
                    "sequence": int(sequence_number),
                    "total_sequences": int(self.total_sequences)
                })
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"SequenceController: Error executing sequence {sequence_number}: {e}")
            return False
    
    async def start_sequence_execution(self):
        """Start sequence execution from current position"""
        if self.current_state != SequenceState.IDLE:
            self.logger.warning("SequenceController: Cannot start - not in IDLE state")
            return False
        
        self.logger.info("SequenceController: Starting sequence execution")
        self.current_state = SequenceState.LOADING
        
        # Load sequence file
        if not self._load_sequence_file():
            self.current_state = SequenceState.ERROR
            return False
        
        # Load current position
        self._load_current_sequence_number()
        
        if self.current_sequence_number >= self.total_sequences:
            self.logger.info("SequenceController: All sequences already completed")
            self.current_state = SequenceState.COMPLETED
            return True
        
        self.current_state = SequenceState.EXECUTING
        self.is_running = True
        
        # Start execution loop
        asyncio.create_task(self._execution_loop())
        
        return True
    
    async def _execution_loop(self):
        """Main execution loop for sequence processing"""
        try:
            while self.is_running and self.current_sequence_number < self.total_sequences:
                if self.current_state == SequenceState.EXECUTING:
                    # Execute current sequence
                    sequence_data = self.sequence_data[self.current_sequence_number]
                    
                    if self._execute_sequence_line(sequence_data):
                        # Move to next sequence
                        self.current_sequence_number += 1
                        self._save_current_sequence_number()
                        
                        self.logger.info(f"SequenceController: Completed sequence {sequence_data.get('sequence_number')}")
                        
                        # Check if we're done
                        if self.current_sequence_number >= self.total_sequences:
                            # Mark as completed, then return to IDLE so future
                            # 'sequence-complete' events can immediately start
                            # a new execution run without requiring an external reset.
                            self.current_state = SequenceState.COMPLETED
                            self.is_running = False
                            self.logger.info("SequenceController: All sequences completed")
                            try:
                                self.logger.send_system_message("sequence_controller", {
                                    "event": "execution-complete",
                                    "total_sequences": int(self.total_sequences)
                                })
                            except Exception:
                                pass
                            
                            # Publish completion event
                            if self.event_bus:
                                await self.event_bus.publish("sequence-execution-complete", True)
                            # Transition to IDLE to signal readiness for next run
                            self.current_state = SequenceState.IDLE
                            break
                        
                        # Respect per-line transition time if provided
                        try:
                            trans_time = float(sequence_data.get("data", {}).get("transTimeSec", self.execution_delay))
                        except Exception:
                            trans_time = self.execution_delay
                        await asyncio.sleep(trans_time)
                    else:
                        self.current_state = SequenceState.ERROR
                        self.is_running = False
                        self.logger.error("SequenceController: Execution failed")
                        break
                
                # Small yield to keep loop responsive
                await asyncio.sleep(0)
                
        except Exception as e:
            self.logger.error(f"SequenceController: Execution loop error: {e}")
            try:
                self.logger.send_system_message("sequence_controller", {
                    "event": "execution-loop-error",
                    "details": str(e)
                })
            except Exception:
                pass
            self.current_state = SequenceState.ERROR
            self.is_running = False
    
    async def pause_execution(self):
        """Pause sequence execution"""
        if self.current_state == SequenceState.EXECUTING:
            self.current_state = SequenceState.PAUSED
            self.logger.info("SequenceController: Execution paused")
            try:
                self.logger.send_system_message("sequence_controller", {
                    "event": "paused",
                    "state": self.current_state,
                    "current_sequence": int(self.current_sequence_number),
                    "total_sequences": int(self.total_sequences)
                })
            except Exception:
                pass
    
    async def resume_execution(self):
        """Resume sequence execution"""
        if self.current_state == SequenceState.PAUSED:
            self.current_state = SequenceState.EXECUTING
            self.logger.info("SequenceController: Execution resumed")
            try:
                self.logger.send_system_message("sequence_controller", {
                    "event": "resumed",
                    "state": self.current_state,
                    "current_sequence": int(self.current_sequence_number),
                    "total_sequences": int(self.total_sequences)
                })
            except Exception:
                pass
    
    async def stop_execution(self):
        """Stop sequence execution"""
        self.is_running = False
        self.current_state = SequenceState.IDLE
        self.logger.info("SequenceController: Execution stopped")
        # Drive actuators to safe state
        self._publish_zero_commands()
        try:
            self.logger.send_system_message("sequence_controller", {
                "event": "stopped",
                "state": self.current_state,
                "current_sequence": int(self.current_sequence_number),
                "total_sequences": int(self.total_sequences)
            })
        except Exception:
            pass
    
    async def reset_execution(self):
        """Reset sequence execution to beginning"""
        self.current_sequence_number = 0
        self._save_current_sequence_number()
        self.current_state = SequenceState.IDLE
        self.is_running = False
        self.logger.info("SequenceController: Execution reset to beginning")
        # Drive actuators to safe state
        self._publish_zero_commands()
        try:
            self.logger.send_system_message("sequence_controller", {
                "event": "reset",
                "state": self.current_state,
                "current_sequence": int(self.current_sequence_number),
                "total_sequences": int(self.total_sequences)
            })
        except Exception:
            pass
    
    def get_status(self) -> dict:
        """Get current status of sequence controller"""
        return {
            "state": self.current_state,
            "current_sequence": self.current_sequence_number,
            "total_sequences": self.total_sequences,
            "is_running": self.is_running,
            "progress": f"{self.current_sequence_number}/{self.total_sequences}" if self.total_sequences > 0 else "0/0"
        }
    
    # Event handlers
    async def handle_sequence_complete(self, data):
        """Handle sequence completion event from AlphaCommsManager"""
        self.logger.info("SequenceController: Received sequence completion event")
        # Reset progress so a fresh sequence starts from 0
        try:
            # Clear persisted progress file if present
            uos.remove(self.state_file_path)
        except Exception:
            pass
        self.current_sequence_number = 0
        await self.start_sequence_execution()
    
    async def handle_stop_command(self, data):
        """Handle stop command - any message triggers stop"""
        self.logger.info("SequenceController: Received stop command")
        await self.stop_execution()
    
    async def handle_pause_command(self, data):
        """Handle pause command - any message triggers pause"""
        self.logger.info("SequenceController: Received pause command")
        await self.pause_execution()
    
    async def handle_resume_command(self, data):
        """Handle resume command - any message triggers resume"""
        self.logger.info("SequenceController: Received resume command")
        await self.resume_execution() 

    # reset command removed as redundant