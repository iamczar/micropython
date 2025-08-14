from tca9535_settings import Register, PinSettings, Port
from tca9535 import TCA9535
from simple_logger import SimpleLogger
from event_bus import EventBus
from command_data_structure import ValveAndAirPumpCmds


class ValveAndAirPumpActuator:
    def __init__(self, event_bus:EventBus, tca9535: TCA9535, logger: SimpleLogger, subscribe_topic: str, publish_topic: str = None):
        """
        Initializes the ValveAndAirPumpActuator with the given parameters.

        :param event_bus: The EventBus instance for subscribing to and publishing events.
        :param tca9535: An instance of TCA9535 to control the valves and air pumps.
        :param logger: An instance of SimpleLogger for logging.
        :param subscribe_topic: The topic to subscribe to for receiving control commands.
        :param publish_topic: The topic to publish status or responses to (optional).
        """
        self.event_bus = event_bus
        self.tca9535 = tca9535
        self.logger = logger
        self.subscribe_topic = subscribe_topic
        self.publish_topic = publish_topic
       
        # Valve to TCA9535 port and pin mapping
        self.valve_pin_map = {
            9: (Port.OUTPUT_PORT_0, PinSettings.Pins.P02),  # PORT0, Pin 2
            8: (Port.OUTPUT_PORT_0, PinSettings.Pins.P03),  # PORT0, Pin 3
            5: (Port.OUTPUT_PORT_0, PinSettings.Pins.P04),  # PORT0, Pin 4
            7: (Port.OUTPUT_PORT_0, PinSettings.Pins.P05),  # PORT0, Pin 5
            3: (Port.OUTPUT_PORT_0, PinSettings.Pins.P06),  # PORT0, Pin 6
            10: (Port.OUTPUT_PORT_0, PinSettings.Pins.P07),  # PORT0, Pin 7
            2: (Port.OUTPUT_PORT_1, PinSettings.Pins.P10),  # PORT1, Pin 2
            4: (Port.OUTPUT_PORT_1, PinSettings.Pins.P11),  # PORT1, Pin 3
            6: (Port.OUTPUT_PORT_1, PinSettings.Pins.P12),  # PORT1, Pin 4
            1: (Port.OUTPUT_PORT_1, PinSettings.Pins.P13),  # PORT1, Pin 5
            11: (Port.OUTPUT_PORT_1, PinSettings.Pins.P14), # airpump 1
            12: (Port.OUTPUT_PORT_1, PinSettings.Pins.P15), # airpump 2
        }
        

        # Initialize the TCA9535 pins (set direction/output state as required)
        self._initialize_pins()

        # Subscribe to the specified topic on the event bus
        self.event_bus.subscribe("valve-airpump-cmds", self.handle_event)

    def _initialize_pins(self):
        """
        Initializes the TCA9535 pins for the valves and air pumps.
        """
        # Step 1: Generate configuration values for both ports using helper functions
        port0_direction = PinSettings.generate_port0_value(
            p00=PinSettings.Direction.OUTPUT, p01=PinSettings.Direction.OUTPUT,
            p02=PinSettings.Direction.OUTPUT, p03=PinSettings.Direction.OUTPUT,
            p04=PinSettings.Direction.OUTPUT, p05=PinSettings.Direction.OUTPUT,
            p06=PinSettings.Direction.OUTPUT, p07=PinSettings.Direction.OUTPUT
        )

        port1_direction = PinSettings.generate_port1_value(
            p10=PinSettings.Direction.OUTPUT, p11=PinSettings.Direction.OUTPUT,
            p12=PinSettings.Direction.OUTPUT, p13=PinSettings.Direction.OUTPUT,
            p14=PinSettings.Direction.OUTPUT, p15=PinSettings.Direction.OUTPUT,
            p16=PinSettings.Direction.OUTPUT, p17=PinSettings.Direction.OUTPUT
        )

        # Step 2: Call configure_all_pins with the generated values
        self.tca9535.configure_all_pins(port0_direction, port1_direction)
        self.tca9535.set_all_pins_to_low()

    async def handle_event(self, data):
        try:
            # Unpack the data into the ValveAndAirPumpCmds structure
            va = ValveAndAirPumpCmds()
            va.unpack(data)
            
            # Set valve and air pump states according to the ValveAndAirPumpCmds unpacked data
            for valve_airpump_index in range(1, 13):  # Valves 1 to 10, Air Pumps 11 and 12
                state = va.get_valve_airpump_state(valve_airpump_index)

                # Set the pin state if the valve or air pump is mapped
                if valve_airpump_index in self.valve_pin_map:
                    port, pin = self.valve_pin_map[valve_airpump_index]
                    pin_state = PinSettings.State.high if state else PinSettings.State.low
                    self.tca9535.set_pin(pin, pin_state, port)
                    
                    va.states
                    
            # Publish the state of each valve and air pump if a publish topic is specified
            # if self.publish_topic:
            #     self.logger.debug(f"valve and air pump states: {va.states}")
            #     await self.event_bus.publish(self.publish_topic, va.states)

        except Exception as e:
            error_msg = f"VA:handle_event:{e}"
            self.logger.error(error_msg)

