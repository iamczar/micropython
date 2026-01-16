class ILEMActuator:
    """
    Actuator for Integrated LEM valves (11–15) using a PCA6408A I/O expander.

    - HIGH = valve open
    - LOW  = valve closed

    The mapping from logical valve IDs to PCA6408A GPIO indices is:
        valve11 -> GPIO 1
        valve12 -> GPIO 2
        valve13 -> GPIO 3
        valve14 -> GPIO 4
        valve15 -> GPIO 5
    """

    def __init__(self, event_bus, pca6408a, logger, subscribe_topic: str):
        from command_data_structure import ILEMValveCmds
        from event_bus import EventBus  # type: ignore
        from pca6408a import PCA6408A  # type: ignore
        from simple_logger import SimpleLogger  # type: ignore

        # Store references without relying on annotations at runtime
        self.event_bus = event_bus  # type: EventBus
        self.expander = pca6408a    # type: PCA6408A
        self.logger = logger        # type: SimpleLogger
        self.subscribe_topic = subscribe_topic

        # Cache class for later instantiation in handle_event
        self._cmd_cls = ILEMValveCmds

        # Valve ID -> PCA6408A GPIO index
        self.valve_to_gpio = {
            11: 1,
            12: 2,
            13: 3,
            14: 4,
            15: 5,
        }

        self._initialize_pins()

        # Subscribe for ILEM valve commands
        self.event_bus.subscribe(self.subscribe_topic, self.handle_event)

    def _initialize_pins(self):
        """
        Configure all PCA6408A pins as outputs and set them low.

        This keeps things simple; unused pins can remain low.
        """
        # 0 = output on PCA6408A CONFIG bits
        self.expander.set_config(0x00)
        # All ILEM valves (GPIO1–GPIO5) start "closed" under active‑low logic:
        # set bits 1–5 high (0b00111110 = 0x3E), others low.
        self.expander.write_outputs(0x3E)

    def set_valve(self, valve_id: int, open_: bool):
        """
        Open/close a single ILEM valve (11–15).
        """
        if valve_id not in self.valve_to_gpio:
            if self.logger:
                self.logger.error(f"ILEMActuator: unknown valve_id {valve_id}")
            return

        gpio = self.valve_to_gpio[valve_id]
        # Invert logical open_/closed before driving GPIO (active‑low coil)
        self.expander.digital_write(gpio, not open_)

    def set_all_closed(self):
        """
        Convenience helper to close all ILEM valves (11–15).
        """
        for valve_id in self.valve_to_gpio:
            self.set_valve(valve_id, False)

    async def handle_event(self, data):
        """
        Handle incoming ILEMValveCmds messages from the event bus.

        Expects `data` to be the packed byte from ILEMValveCmds.pack().
        """
        try:
            cmd = self._cmd_cls()
            cmd.unpack(data)

            # Apply each valve state via set_valve (which handles inversion).
            for valve_id in self.valve_to_gpio:
                state = cmd.get_valve_state(valve_id)
                self.set_valve(valve_id, state)

            # Send status/ack message directly to host via logger/system stream.
            if self.logger:
                valve_states = {}
                for valve_id in self.valve_to_gpio.keys():
                    valve_states[valve_id] = bool(cmd.get_valve_state(valve_id))
                self.logger.send_system_message(
                    "ilem_actuator",
                    {
                        "event": "ilem_cmd_ack",
                        "stage": "ilem_actuator",
                        "kind": "valve_states",
                        "raw_states": cmd.states,
                        "valves": valve_states,
                    },
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"ILEMActuator.handle_event error: {e}")


