"""
SequenceController - State-per-class architecture (aligned with AlphaCommsManager)

Goals:
- Clear state separation: Idle, Loading, Executing, Paused, Completed, Error
- Start/pause/resume/stop commands via event bus handlers
- Pause behavior: stop motors and wrist; preserve current valve/air pump states
- Load sequence from JSONL file and persist current sequence number
- Periodic status heartbeat for host visibility (runs regardless of state)
"""

import uasyncio as asyncio
import uos
import json
import time
import utime
from event_bus import EventBus
from simple_logger import SimpleLogger
from command_data_structure import (
    OxyPumpCmds, PressurePumpCmds, ValveAndAirPumpCmds,
)


class State:
    """Base state class for SequenceController."""

    def __init__(self, context: "SequenceController"):
        self.context = context
        self.logger = context.logger

    async def enter(self):
        pass

    async def exit(self):
        pass

    async def on_pause(self):
        pass

    async def on_resume(self):
        pass

    async def on_stop(self):
        pass

    async def on_start(self):
        pass


class IdleState(State):
    async def enter(self):
        await self.context._send_state("idle", {"action": "entered_idle"})

    async def on_start(self):
        await self.context._transition("loading")


class LoadingState(State):
    async def enter(self):
        await self.context._send_state("loading", {"action": "loading_sequence"})
        ok = self.context.load_sequence_file()
        if not ok:
            self.logger.error("SequenceController: Failed to load sequence file")
            await self.context._transition("error")
            return
        self.context._load_current_sequence_number()
        # If already complete, mark completed; otherwise start
        if self.context.current_sequence_number >= self.context.total_sequences:
            await self.context._transition("completed")
        else:
            await self.context._transition("executing")

    async def on_stop(self):
        await self.context._transition("idle")


class ExecutingState(State):
    def __init__(self, context):
        super().__init__(context)
        self._task = None

    async def enter(self):
        await self.context._send_state("executing", {
            "current_sequence": int(self.context.current_sequence_number),
            "total_sequences": int(self.context.total_sequences),
        })
        self.context.is_running = True
        # Kick off execution loop
        self._task = asyncio.create_task(self._execution_loop())

    async def exit(self):
        # Let the loop check flags and exit naturally
        pass

    async def on_pause(self):
        await self.context._transition("paused")

    async def on_stop(self):
        await self.context._transition("idle")

    async def _execution_loop(self):
        try:
            while self.context.current_sequence_number < self.context.total_sequences:
                # Exit loop if state changed away from Executing
                if not isinstance(self.context.state, ExecutingState):
                    return

                # If not currently holding, dispatch the current line
                if self.context._hold_remaining_ms <= 0:
                    data = self.context.sequence_data[self.context.current_sequence_number]
                    ok = self.context._execute_sequence_line(data)
                    if not ok:
                        self.logger.error("SequenceController: Execution of line failed")
                        await self.context._transition("error")
                        return
                    # Initialize hold time
                    try:
                        trans_time = float(data.get("data", {}).get("transTimeSec", self.context.execution_delay))
                    except Exception:
                        trans_time = self.context.execution_delay
                    self.context._hold_remaining_ms = int(trans_time * 1000)
                    # Set an absolute deadline to make heartbeats consistent
                    self.context._hold_until_ms = utime.ticks_add(utime.ticks_ms(), self.context._hold_remaining_ms)

                # Hold in small chunks to be responsive to pause
                sleep_ms = 100 if self.context._hold_remaining_ms > 100 else self.context._hold_remaining_ms
                if sleep_ms > 0:
                    await asyncio.sleep(sleep_ms / 1000.0)
                    # If state changed (e.g., paused), leave remaining hold as-is
                    if not isinstance(self.context.state, ExecutingState):
                        return
                    self.context._hold_remaining_ms -= sleep_ms
                else:
                    # Done holding for this line; advance
                    self.context._hold_remaining_ms = 0
                    self.context._hold_until_ms = 0
                    self.context.current_sequence_number += 1
                    self.context._save_current_sequence_number()
                    if self.context.current_sequence_number >= self.context.total_sequences:
                        await self.context._transition("completed")
                        return
                await asyncio.sleep(0)
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Execution loop error: {e}")
            except Exception:
                pass
            await self.context._transition("error")


class PausedState(State):
    async def enter(self):
        # Stop pumps only; preserve valves/air pumps and keep wrist at last command
        self.context._publish_pause_commands()
        await self.context._send_state("paused", {
            "current_sequence": int(self.context.current_sequence_number),
            "total_sequences": int(self.context.total_sequences),
        })

    async def on_resume(self):
        await self.context._transition("executing")

    async def on_stop(self):
        await self.context._transition("idle")


class CompletedState(State):
    async def enter(self):
        self.context.is_running = False
        await self.context._send_state("completed", {
            "total_sequences": int(self.context.total_sequences)
        })
        # Transition to idle ready for next run
        await self.context._transition("idle")


class ErrorState(State):
    async def enter(self):
        self.context.is_running = False
        await self.context._send_state("error", {})
        # Drive actuators to safe state
        self.context._publish_zero_commands()

    async def on_stop(self):
        await self.context._transition("idle")


class SequenceController:
    def __init__(self, event_bus: EventBus = None, logger: SimpleLogger = None):
        self.event_bus = event_bus
        self.logger = logger or SimpleLogger("SequenceController")
        
        # Files
        self.sequence_file_path = "/sd/sequences/current_sequence.json"
        self.state_file_path = "/sd/sequences/current_sequence_number.txt"
        
        # State
        self.sequence_data = []
        self.current_sequence_number = 0
        self.total_sequences = 0
        self.is_running = False
        self.execution_delay = 1.0

        # Last dispatched commands (for pause behavior)
        self._last_oxy_cmd = None
        self._last_pressure_cmd = None
        self._last_va_cmd = None
        self._last_wrist_cmd = 0

        # Heartbeat
        self.status_interval = 1.0
        self._status_task = None
        
        # Remaining hold time for current line (milliseconds)
        self._hold_remaining_ms = 0
        self._hold_until_ms = 0

        # Init FS
        self._init_fs()

        # Build states and set initial
        self.states = {
            "idle": IdleState(self),
            "loading": LoadingState(self),
            "executing": ExecutingState(self),
            "paused": PausedState(self),
            "completed": CompletedState(self),
            "error": ErrorState(self),
        }
        self.state: State = self.states["idle"]

        # Subscriptions
        if self.event_bus:
            self._subscribe()

        # Start heartbeat and enter idle
        self._start_heartbeat()
        asyncio.create_task(self.state.enter())

    # ------------- Event bus wiring -------------
    def _subscribe(self):
        self.event_bus.subscribe("sequence-complete", self._on_sequence_complete)
        self.event_bus.subscribe("stop-cmd", self.handle_stop_command)
        self.event_bus.subscribe("pause-cmd", self.handle_pause_command)
        self.event_bus.subscribe("resume-cmd", self.handle_resume_command)

    async def _on_sequence_complete(self, data):
        # Clear progress and start a new execution automatically
        try:
            uos.remove(self.state_file_path)
        except Exception:
            pass
        self.current_sequence_number = 0
        await self.start_sequence_execution()

    # Public handlers (called by event bus)
    async def handle_stop_command(self, data):
        await self._delegate("on_stop")

    async def handle_pause_command(self, data):
        await self._delegate("on_pause")

    async def handle_resume_command(self, data):
        await self._delegate("on_resume")

    async def start_sequence_execution(self):
        await self._delegate("on_start")

    # ------------- State transitions -------------
    async def _transition(self, next_name: str):
        try:
            await self.state.exit()
        except Exception:
            pass
        self.state = self.states.get(next_name, self.states["error"])
        # State-specific flags
        if next_name == "idle":
            self.is_running = False
        elif next_name == "executing":
            self.is_running = True
        try:
            await self.state.enter()
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Error entering state {next_name}: {e}")
            except Exception:
                pass
            # Fallback to error state
            self.state = self.states["error"]
            try:
                await self.state.enter()
            except Exception:
                pass

    async def _delegate(self, method_name: str):
        # Ensure stop always drives actuators to safe state
        if method_name == "on_stop":
            try:
                self._publish_zero_commands()
            except Exception:
                pass
            await self._transition("idle")
            return
        method = getattr(self.state, method_name, None)
        if method is not None:
            try:
                await method()
            except Exception as e:
                try:
                    self.logger.error(f"SequenceController: Delegate {method_name} failed: {e}")
                except Exception:
                    pass
                await self._transition("error")

    # ------------- IO and status -------------
    def _init_fs(self):
        try:
            try:
                uos.mkdir("/sd/sequences")
            except OSError:
                pass
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: FS init error: {e}")
            except Exception:
                pass

    def _send_system(self, payload: dict):
        try:
            # Tag must remain 'sequence_controller' for host compatibility
            self.logger.send_system_message("sequence_controller", payload)
        except Exception:
            pass

    async def _send_state(self, name: str, payload: dict):
        try:
            out = {
                "event": "status",
                "state": name,
                "current_sequence": int(self.current_sequence_number),
                "total_sequences": int(self.total_sequences),
                "is_running": bool(self.is_running),
                # Report remaining hold time in seconds only
                "hold_remaining_sec": int((self._hold_remaining_ms or 0) / 1000),
            }
            if payload:
                out.update(payload)
            self._send_system(out)
        except Exception:
            pass

    def _start_heartbeat(self):
        if self._status_task is None:
            self._status_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        while True:
            try:
                # Report the actual current state name on each heartbeat
                state_name = self.state.__class__.__name__.replace("State", "").lower()
                # Recompute remaining ms based on deadline if available
                if getattr(self, "_hold_until_ms", 0) and isinstance(self.state, ExecutingState):
                    now_ms = utime.ticks_ms()
                    remaining = int(self._hold_until_ms - now_ms)
                    self._hold_remaining_ms = remaining if remaining > 0 else 0
                await self._send_state(state_name, {})
            except Exception:
                pass
            await asyncio.sleep(self.status_interval)

    # ------------- Persistence -------------
    def _save_current_sequence_number(self):
        try:
            with open(self.state_file_path, "w") as f:
                f.write(str(self.current_sequence_number))
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Save seq num error: {e}")
            except Exception:
                pass
    
    def _load_current_sequence_number(self):
        try:
            with open(self.state_file_path, "r") as f:
                content = f.read().strip()
                self.current_sequence_number = int(content) if content else 0
        except Exception:
            self.current_sequence_number = 0
    
    def load_sequence_file(self) -> bool:
        try:
            self.sequence_data = []
            with open(self.sequence_file_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "sequence_number" in data and ("data" in data or "state" in data):
                            if "state" in data and "data" not in data:
                                data = {"sequence_number": data["sequence_number"], "data": data["state"]}
                            self.sequence_data.append(data)
                        else:
                            self.logger.warning(f"SC: Invalid JSONL line {line_num}")
                    except Exception as e:
                        self.logger.warning(f"SC: JSON parse error line {line_num}: {e}")
            self.total_sequences = len(self.sequence_data)
            return True
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Load file error: {e}")
            except Exception:
                pass
            return False
    
    # ------------- Command publishing -------------
    def _publish_zero_commands(self):
        try:
            oxy = OxyPumpCmds()
            oxy.circFlowSpeed = 0
            oxy.oxySP = oxy.oxyKp = oxy.oxyKi = oxy.oxyKd = 0.0
            oxy.pump1dir = 0
            oxy.tube_bore = 1
            oxy.pump_2_speed_ratio = 0.0

            pres = PressurePumpCmds()
            pres.pressureFlowSpeed = 0
            pres.pressureSP = pres.pressureKp = pres.pressureKi = pres.pressureKd = 0.0
            pres.pump2dir = 0
            pres.tube_bore = 1

            va = ValveAndAirPumpCmds()
            for idx in range(1, 10 + 1):
                va.set_valve_air_pump(idx, 0)
            va.set_valve_air_pump(ValveAndAirPumpCmds.airpump1, 0)
            va.set_valve_air_pump(ValveAndAirPumpCmds.airpump2, 0)

            wrist = 0

            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("oxy-pump-cmds", oxy.pack()))
                asyncio.create_task(self.event_bus.publish("pressure-pump-cmd", pres.pack()))
                asyncio.create_task(self.event_bus.publish("valve-airpump-cmds", va.pack()))
                asyncio.create_task(self.event_bus.publish("wrist-cmds", wrist))
        except Exception:
            pass

    def _publish_pause_commands(self):
        try:
            oxy = OxyPumpCmds()
            if self._last_oxy_cmd is not None:
                oxy.oxySP = float(self._last_oxy_cmd.oxySP)
                oxy.oxyKp = float(self._last_oxy_cmd.oxyKp)
                oxy.oxyKi = float(self._last_oxy_cmd.oxyKi)
                oxy.oxyKd = float(self._last_oxy_cmd.oxyKd)
                oxy.pump1dir = int(self._last_oxy_cmd.pump1dir)
                oxy.tube_bore = int(self._last_oxy_cmd.tube_bore)
                oxy.pump_2_speed_ratio = float(self._last_oxy_cmd.pump_2_speed_ratio)
            oxy.circFlowSpeed = 0

            pres = PressurePumpCmds()
            if self._last_pressure_cmd is not None:
                pres.pressureSP = float(self._last_pressure_cmd.pressureSP)
                pres.pressureKp = float(self._last_pressure_cmd.pressureKp)
                pres.pressureKi = float(self._last_pressure_cmd.pressureKi)
                pres.pressureKd = float(self._last_pressure_cmd.pressureKd)
                pres.pump2dir = int(self._last_pressure_cmd.pump2dir)
                pres.tube_bore = int(self._last_pressure_cmd.tube_bore)
            pres.pressureFlowSpeed = 0

            # Do not touch wrist or valves/air pumps on pause
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("oxy-pump-cmds", oxy.pack()))
                asyncio.create_task(self.event_bus.publish("pressure-pump-cmd", pres.pack()))
        except Exception:
            pass

    def _execute_sequence_line(self, sequence_data: dict) -> bool:
        try:
            seq_num = sequence_data.get("sequence_number")
            data = sequence_data.get("data", {})
            
            # Oxy pump
            oxy_cmd = OxyPumpCmds()
            oxy_cmd.circFlowSpeed = int(data.get("circFlow", 0))
            oxy_cmd.oxySP = float(data.get("oxySP", 0.0))
            oxy_cmd.oxyKp = float(data.get("oxyKp", 0.0))
            oxy_cmd.oxyKi = float(data.get("oxyKi", 0.0))
            oxy_cmd.oxyKd = float(data.get("oxyKd", 0.0))
            oxy_cmd.pump1dir = 1 if data.get("pump1Dir", True) else 0
            oxy_cmd.tube_bore = int(data.get("tube_bore", 1))
            oxy_cmd.pump_2_speed_ratio = float(data.get("pump_2_speed_ratio", 1.0))
            
            # Pressure pump
            pres_cmd = PressurePumpCmds()
            pres_cmd.pressureFlowSpeed = int(data.get("pressureFlow", 0))
            pres_cmd.pressureSP = float(data.get("pressureSP", 0.0))
            pres_cmd.pressureKp = float(data.get("pressureKp", 0.0))
            pres_cmd.pressureKi = float(data.get("pressureKi", 0.0))
            pres_cmd.pressureKd = float(data.get("pressureKd", 0.0))
            pres_cmd.pump2dir = 1 if data.get("pump2Dir", True) else 0
            pres_cmd.tube_bore = int(data.get("tube_bore", 1))
            
            # Valves and air pumps
            va_cmd = ValveAndAirPumpCmds()
            for idx in range(1, 11):
                key = f"valve{idx}"
                if key in data:
                    va_cmd.set_valve_air_pump(idx, 1 if data.get(key) else 0)
            if "airpump1" in data:
                va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump1, 1 if data.get("airpump1") else 0)
            if "airpump2" in data:
                va_cmd.set_valve_air_pump(ValveAndAirPumpCmds.airpump2, 1 if data.get("airpump2") else 0)
            
            # Wrist
            wrist_cmd = int(data.get("wristCmd", 0))
            
            # Publish
            if self.event_bus:
                asyncio.create_task(self.event_bus.publish("oxy-pump-cmds", oxy_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("pressure-pump-cmd", pres_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("valve-airpump-cmds", va_cmd.pack()))
                asyncio.create_task(self.event_bus.publish("wrist-cmds", wrist_cmd))

            # Remember last
            self._last_oxy_cmd = oxy_cmd
            self._last_pressure_cmd = pres_cmd
            self._last_va_cmd = va_cmd
            self._last_wrist_cmd = wrist_cmd

            # System log (lightweight)
            self._send_system({
                    "event": "dispatched",
                "sequence": int(seq_num) if seq_num is not None else -1,
                "total_sequences": int(self.total_sequences),
            })
            return True
        except Exception as e:
            try:
                self.logger.error(f"SequenceController: Execute error: {e}")
            except Exception:
                pass
            return False


