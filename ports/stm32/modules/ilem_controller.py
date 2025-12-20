import uasyncio as asyncio

from event_bus import EventBus
from simple_logger import SimpleLogger


class ILEMController:
    """
    Integrated LEM controller.

    Responsibilities:
    - Listen for high-level ILEM commands on 'lem-cmd' from AlphaCommsManager.
    - Observe Cycler state via:
        * 'file-transfer-status'  (sequence file transfer via AlphaCommsManager)
        * 'sequence-status'       (live sequence execution via SequenceController)
    - Decide whether the Cycler is idle enough to execute the command (FR6).
    - Always send an acknowledgement for each received command via
      SimpleLogger.send_system_message('ilem_controller', ...),
      which the host routes to 'ilem-status/<module_id>'.

    NOTE: This first version only handles gating + acks; valve/pump control
    will be layered on top once the basic command path is validated.
    """

    def __init__(self, event_bus: EventBus, logger: SimpleLogger, tube_bore=None, pump_speed_hz=None):
        self.event_bus = event_bus
        self.logger = logger

        # Latest known states
        self._file_transfer_state = "idle"     # AlphaCommsManager state
        self._sequence_state = "idle"          # SequenceController state

        # Pump/flow calibration for ILEM dispense
        # Microsteps per revolution: 8 microsteps * 200 steps
        self._microsteps_per_rev = 8 * 200
        # Tube bore mapping reused from CircFlowController (µL / revolution)
        self._tube_bore_map = {
            1: 170.0,   # 1.6mm
            2: 320.0,   # 2.4mm
            3: 495.0,   # 3.2mm
            4: 655.7,   # 4.8mm
        }
        # Calibrated tube_bore and rate
        try:
            tb = int(tube_bore) if tube_bore is not None else 3
        except Exception:
            tb = 3
        self._tube_bore = tb
        self._tube_rate_ul_per_rev = self._tube_bore_map.get(self._tube_bore, self._tube_bore_map[3])

        # Fixed pump speed for ILEM dispense (Hz, i.e. microsteps/second)
        try:
            self._pump_speed_hz = float(pump_speed_hz) if pump_speed_hz is not None else 1100.0
        except Exception:
            self._pump_speed_hz = 1100.0

        # Track an active dispense task so STOP can cancel it
        self._active_dispense_task = None

        # Subscribe to internal status topics
        self.event_bus.subscribe("file-transfer-status", self._on_file_transfer_status)
        self.event_bus.subscribe("sequence-status", self._on_sequence_status)
        self.event_bus.subscribe("lem-cmd", self._on_lem_cmd)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _is_transfer_busy(self) -> bool:
        """
        Treat AlphaCommsManager states that imply an active transfer as busy.
        """
        state = (self._file_transfer_state or "").lower()
        return state in ("waiting_for_sequence", "receiving_sequence")

    def _is_sequence_busy(self) -> bool:
        """
        Treat SequenceController states that imply an active sequence as busy.
        """
        state = (self._sequence_state or "").lower()
        return state in ("loading", "executing", "paused")

    def _is_cycler_idle(self) -> bool:
        return not (self._is_transfer_busy() or self._is_sequence_busy())

    # ------------------------------------------------------------------
    # Valve helpers
    # ------------------------------------------------------------------
    def _build_valve_payload(self, action: str, cmd: dict):
        """
        Placeholder helper that builds the bytes payload we would send to
        'lem-actuator' (ILEMActuator) using ILEMValveCmds.

        This builds the packed bytes that are sent to 'lem-actuator'
        (ILEMActuator) and also mirrored into acks for debugging.
        """
        try:
            from command_data_structure import ILEMValveCmds
        except Exception:
            return None

        valves = ILEMValveCmds()

        # Start with all ILEM valves 11–15 closed
        for v in (ILEMValveCmds.valve11,
                  ILEMValveCmds.valve12,
                  ILEMValveCmds.valve13,
                  ILEMValveCmds.valve14,
                  ILEMValveCmds.valve15):
            valves.set_valve(v, False)

        if action == "dispense":
            # Map UI bottle (1–4) to media valves 11–14
            bottle = int(cmd.get("bottle", 0) or 0)
            bottle_to_valve = {
                1: ILEMValveCmds.valve11,
                2: ILEMValveCmds.valve12,
                3: ILEMValveCmds.valve13,
                4: ILEMValveCmds.valve14,
            }
            media_valve = bottle_to_valve.get(bottle)
            if media_valve is not None:
                valves.set_valve(media_valve, True)
            # Valve15 is the common valve, automatically open during dispense
            valves.set_valve(ILEMValveCmds.valve15, True)
        elif action == "stop":
            # All closed; nothing to do beyond the initial reset above.
            pass

        try:
            return valves.pack()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Pump helpers (ILEM dispense profile + runtime task)
    # ------------------------------------------------------------------

    def _compute_pump_profile(self, action: str, cmd: dict):
        """
        Compute (direction, speed_hz, pump_2_speed_ratio, duration_sec)
        for an ILEM command.

        duration_sec is only meaningful for "dispense".
        """
        # Pump 1 backwards for ILEM dispense; forward/backward mapping
        # follows PumpDirection in PumpActuator.
        direction_backward = False

        if action == "dispense":
            try:
                volume_ml = float(cmd.get("volume_ml", 0.0) or 0.0)
            except Exception:
                volume_ml = 0.0

            if volume_ml <= 0.0:
                return None

            tube_rate = float(self._tube_rate_ul_per_rev or 0.0)
            if tube_rate <= 0.0:
                return None

            speed_hz = float(self._pump_speed_hz)
            if speed_hz <= 0.0:
                return None

            # Convert volume to µL
            volume_ul = volume_ml * 1000.0
            # Flow (µL/s) at speed_hz microsteps/s:
            # Q = (speed_hz / microsteps_per_rev) * tube_rate_ul_per_rev
            flow_ul_per_sec = (speed_hz / float(self._microsteps_per_rev)) * tube_rate
            if flow_ul_per_sec <= 0.0:
                return None

            # Duration to deliver volume_ul at this flow
            duration_sec = volume_ul / flow_ul_per_sec

            # Guard against extreme durations
            duration_sec = max(0.1, min(duration_sec, 3600.0))

            pump_2_speed_ratio = 0.0
            return (direction_backward, speed_hz, pump_2_speed_ratio, duration_sec)

        elif action == "stop":
            # Explicit STOP for Pump 1: use speed_hz = 1 (per pump driver semantics)
            # and pump_2_speed_ratio = 0.0. No duration for STOP.
            return (direction_backward, 1, 0.0, 0.0)

        return None

    def _build_pump_payload(self, action: str, cmd: dict):
        """
        Build the tuple we would send to 'oxy-pump-01-act'.

        Expected format (matching CircFlowController):
            (direction: bool, speed_hz: int, pump_2_speed_ratio: float)

        This helper is used to mirror would-be pump commands into acks for
        debugging. The actual runtime behaviour for DISPENSE is managed by
        an internal asyncio task started from _on_lem_cmd.
        """
        profile = self._compute_pump_profile(action, cmd)
        if profile is None:
            return None
        direction_backward, speed_hz, pump_2_speed_ratio, _ = profile
        return (direction_backward, int(speed_hz), float(pump_2_speed_ratio))

    def _build_manifold_valve_payload(self, action: str):
        """
        Build a ValveAndAirPumpCmds payload for the main manifold (valves 1–10).

        FR4 requires that during an ILEM dispense we ensure:
          - valve1, valve3, valve4 and valve7 are effectively closed.

        We achieve this by:
          - Explicitly setting bits for valves 1, 3 and 7 to 1 (they are
            normally‑open, so 1 = closed).
          - Leaving valve4 at 0 (it is normally‑closed, so 0 = closed).

        For STOP, we keep these valves in a safe (closed) state as well, but
        do not attempt to reopen anything; normal Cycler sequence control
        will reassert valve patterns afterwards.
        """
        try:
            from command_data_structure import ValveAndAirPumpCmds
        except Exception:
            return None

        va = ValveAndAirPumpCmds()

        if action == "dispense":
            # DISPENSE: enforce FR4 safety by closing valve1, valve3 and valve7.
            # These are normally-open valves, so bit 1 (HIGH) = closed.
            try:
                va.set_valve_air_pump(ValveAndAirPumpCmds.valve1, 1)
                va.set_valve_air_pump(ValveAndAirPumpCmds.valve3, 1)
                va.set_valve_air_pump(ValveAndAirPumpCmds.valve7, 1)
                # Valve4 is normally-closed; default 0 already means closed.
            except Exception:
                pass
        elif action == "stop":
            # STOP: de‑energise all manifold valves (all bits 0); do not set any
            # bits here so ValveAndAirPumpCmds.states remains 0.
            pass

        try:
            return va.pack()
        except Exception:
            return None

    async def _send_pump_and_valve_stop(self):
        """
        Send STOP commands to pump and valves to leave ILEM in a safe state.
        """
        try:
            # Pump STOP
            stop_profile = self._compute_pump_profile("stop", {})
            if stop_profile is not None and self.event_bus:
                d, s, r, _ = stop_profile
                await self.event_bus.publish("oxy-pump-01-act", (d, int(s), float(r)))
        except Exception:
            pass

        # ILEM valves: all closed
        try:
            valve_payload = self._build_valve_payload("stop", {})
            if valve_payload is not None and self.event_bus:
                await self.event_bus.publish("lem-actuator", valve_payload)
        except Exception:
            pass

        # Manifold safety frame: STOP state (all bits 0)
        try:
            manifold_payload = self._build_manifold_valve_payload("stop")
            if manifold_payload is not None and self.event_bus:
                await self.event_bus.publish("valve-airpump-cmds", manifold_payload)
        except Exception:
            pass

    async def _dispense_task(self, cmd: dict, profile, valve_payload, manifold_payload):
        """
        Long-running task that owns a single ILEM dispense:
          - Opens ILEM + manifold valves
          - Starts Pump 1 at the computed speed
          - Waits for the computed duration
          - Sends STOP to pump and valves
        """
        try:
            direction_backward, speed_hz, pump_2_speed_ratio, duration_sec = profile

            # Apply ILEM valves
            try:
                if valve_payload is not None and self.event_bus:
                    await self.event_bus.publish("lem-actuator", valve_payload)
            except Exception:
                pass

            # Apply manifold safety frame
            try:
                if manifold_payload is not None and self.event_bus:
                    await self.event_bus.publish("valve-airpump-cmds", manifold_payload)
            except Exception:
                pass

            # Start Pump 1
            try:
                if self.event_bus:
                    await self.event_bus.publish(
                        "oxy-pump-01-act",
                        (direction_backward, int(speed_hz), float(pump_2_speed_ratio)),
                    )
            except Exception:
                pass

            # Wait for duration, allowing cancellation
            remaining = float(duration_sec or 0.0)
            while remaining > 0:
                step = 0.5 if remaining > 0.5 else remaining
                await asyncio.sleep(step)
                remaining -= step

            # On normal completion, send STOP
            await self._send_pump_and_valve_stop()

        except asyncio.CancelledError:
            # STOP handler will take care of safe shutdown; just exit.
            raise
        except Exception as e:
            try:
                self.logger.error(f"ILEMController._dispense_task error: {e}")
            except Exception:
                pass
            # Best-effort safe stop
            try:
                await self._send_pump_and_valve_stop()
            except Exception:
                pass
        finally:
            # Clear active task reference
            self._active_dispense_task = None

    def _start_dispense_task(self, cmd: dict, profile, valve_payload, manifold_payload):
        """
        Start a new dispense task if none is active.
        """
        # Avoid overlapping dispenses; if one is already running, we do not start another.
        if self._active_dispense_task is not None:
            try:
                self.logger.error("ILEMController: dispense requested while another is active")
            except Exception:
                pass
            return False

        try:
            task = asyncio.create_task(self._dispense_task(cmd, profile, valve_payload, manifold_payload))
        except Exception as e:
            try:
                self.logger.error(f"ILEMController: unable to start dispense task: {e}")
            except Exception:
                pass
            return False

        self._active_dispense_task = task
        return True

    async def _cancel_dispense_if_any(self):
        """
        Cancel an active dispense task (if present) and send STOP to pump/valves.
        """
        task = self._active_dispense_task
        self._active_dispense_task = None
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass
        # In all cases, enforce STOP on pump + valves
        try:
            await self._send_pump_and_valve_stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # EventBus handlers
    # ------------------------------------------------------------------
    async def _on_file_transfer_status(self, data):
        try:
            if isinstance(data, dict):
                self._file_transfer_state = str(data.get("state", self._file_transfer_state))
        except Exception:
            # Leave last-known state unchanged on parse errors
            pass

    async def _on_sequence_status(self, data):
        try:
            if isinstance(data, dict):
                self._sequence_state = str(data.get("state", self._sequence_state))
        except Exception:
            pass

    async def _on_lem_cmd(self, cmd):
        """
        Handle a high-level ILEM command published on 'lem-cmd' by AlphaCommsManager.

        cmd is expected to be the inner 'message' dict from the Alpha envelope,
        e.g. { "command": "lem_cmd", "action": "dispense" | "stop", ... }.
        """
        try:
            if not isinstance(cmd, dict):
                cmd = {} if cmd is None else {"raw": cmd}

            action = str(cmd.get("action", "")).lower()
            # Basic echo of the user-visible intent for diagnostics
            original = dict(cmd)

            cycler_idle = self._is_cycler_idle()
            accepted = False
            reason = None
            valve_payload = None
            pump_payload = None
            manifold_payload = None

            if not cycler_idle:
                # Reject when Cycler is busy with transfer or live sequence (FR6)
                if self._is_transfer_busy():
                    reason = "Unable to execute ILEM command – live transfer in process, Cycler must be idle."
                elif self._is_sequence_busy():
                    reason = "Unable to execute ILEM command – live sequence in process, Cycler must be idle."
                else:
                    reason = "Unable to execute ILEM command – Cycler not idle."
            else:
                # Build placeholder payloads for debug/ack, and if action is
                # 'dispense' schedule a runtime dispense task. For 'stop' we
                # immediately cancel any active dispense and force a STOP on
                # pump + valves.
                try:
                    valve_payload = self._build_valve_payload(action, cmd)
                except Exception:
                    valve_payload = None
                try:
                    pump_payload = self._build_pump_payload(action, cmd)
                except Exception:
                    pump_payload = None
                try:
                    manifold_payload = self._build_manifold_valve_payload(action)
                except Exception:
                    manifold_payload = None

                if action == "dispense":
                    # Compute pump profile (including duration) and start a
                    # background dispense task if possible.
                    profile = self._compute_pump_profile(action, cmd)
                    if profile is None:
                        reason = "Unable to execute ILEM command – invalid volume or calibration."
                    else:
                        started = self._start_dispense_task(cmd, profile, valve_payload, manifold_payload)
                        if started:
                            accepted = True
                            reason = "ILEM command accepted (valve + pump control active)."
                        else:
                            reason = "Unable to execute ILEM command – another dispense is already active."
                elif action == "stop":
                    # Cancel any active dispense and send STOP to pump/valves
                    await self._cancel_dispense_if_any()
                    accepted = True
                    reason = "ILEM STOP command accepted; dispense stopped and valves set safe."

            ack = {
                "event": "ilem_cmd_ack",
                "stage": "ilem_controller",
                "accepted": bool(accepted),
                "cycler_idle": bool(cycler_idle),
                "file_transfer_state": self._file_transfer_state,
                "sequence_state": self._sequence_state,
                "action": action,
                "original_cmd": original,
            }
            if reason:
                ack["reason"] = reason
            # Include placeholder payloads so host/debug tooling can see what
            # would be sent once execution is enabled.
            if valve_payload is not None:
                ack["placeholder_valve_payload"] = list(valve_payload)
            if pump_payload is not None:
                d, s, r = pump_payload
                ack["placeholder_pump_payload"] = {
                    "direction_backward": bool(d),
                    "speed_hz": int(s),
                    "pump_2_speed_ratio": float(r),
                }
            if manifold_payload is not None:
                ack["placeholder_manifold_valve_payload"] = list(manifold_payload)

            try:
                self.logger.send_system_message("ilem_controller", ack)
            except Exception:
                pass

        except Exception as e:
            # Ensure we at least emit a failure ack so the host is not left hanging
            try:
                self.logger.send_system_message(
                    "ilem_controller",
                    {
                        "event": "ilem_cmd_ack",
                        "accepted": False,
                        "reason": f"ILEMController internal error: {e}",
                    },
                )
            except Exception:
                pass


