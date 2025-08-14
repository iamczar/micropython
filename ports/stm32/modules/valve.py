from pyb import Pin
from simple_logger import SimpleLogger as Logger

class ValveActuator:
    def __init__(self, name, control_pin, state_pin, logger=None, pull=None):
        self.name = name
        self.control_pin = Pin(control_pin, Pin.OUT_PP)
        self.state_pin = Pin(state_pin, Pin.IN, pull)
        self.logger = logger or Logger(name).get_logger()
        self.logger.info(f"{self.name} initialized with control pin {control_pin} and state pin {state_pin} with pull {pull}")

    def open(self):
        self.control_pin.high()
        self.logger.info(f"{self.name} valve opened")

    def close(self):
        self.control_pin.low()
        self.logger.info(f"{self.name} valve closed")

    def get_state(self):
        state = "open" if self.state_pin.value() else "closed"
        self.logger.info(f"{self.name} valve state is {state}")
        return state
