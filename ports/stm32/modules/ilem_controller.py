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

    def __init__(self, event_bus: EventBus, logger: SimpleLogger):
        self.event_bus = event_bus
        self.logger = logger

        # Latest known states
        self._file_transfer_state = "idle"     # AlphaCommsManager state
        self._sequence_state = "idle"          # SequenceController state

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
    # Placeholder helpers for future valve + pump control
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

    def _build_pump_payload(self, action: str, cmd: dict):
        """
        Placeholder helper that builds the tuple we would send to
        'oxy-pump-01-act'.

        Expected format (matching CircFlowController):
            (direction: bool, speed_hz: int, pump_2_speed_ratio: float)

        For now, this does NOT attempt to compute real speed/duration from
        volume_ml; that calibration will be added later.
        """
        # Pump 1 backwards for ILEM dispense; forward/backward mapping follows PumpDirection
        direction_backward = False

        if action == "dispense":
            try:
                volume_ml = float(cmd.get("volume_ml", 0.0) or 0.0)
            except Exception:
                volume_ml = 0.0
            # TODO: derive speed_hz and duration from volume_ml and calibration constants.
            # For now, use a safe placeholder of 0 Hz (no motion).
            speed_hz = 0
            pump_2_speed_ratio = 0.0
            return (direction_backward, speed_hz, pump_2_speed_ratio)
        elif action == "stop":
            # Explicit stop: 0 Hz, ratio 0
            return (direction_backward, 0, 0.0)

        return None

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

            if not cycler_idle:
                # Reject when Cycler is busy with transfer or live sequence (FR6)
                if self._is_transfer_busy():
                    reason = "Unable to execute ILEM command – live transfer in process, Cycler must be idle."
                elif self._is_sequence_busy():
                    reason = "Unable to execute ILEM command – live sequence in process, Cycler must be idle."
                else:
                    reason = "Unable to execute ILEM command – Cycler not idle."
            else:
                # For now we only implement valve control; pump behaviour will
                # be added once volume->speed/duration calibration is agreed.
                accepted = True
                reason = "ILEM command accepted (valve control active, pump control TBD)."
                try:
                    valve_payload = self._build_valve_payload(action, cmd)
                except Exception:
                    valve_payload = None
                try:
                    pump_payload = self._build_pump_payload(action, cmd)
                except Exception:
                    pump_payload = None

                # Apply valve state immediately via ILEMActuator
                try:
                    if valve_payload is not None and self.event_bus:
                        await self.event_bus.publish("lem-actuator", valve_payload)
                except Exception:
                    # Keep going so we still emit an ack even if valve publish fails
                    pass

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


