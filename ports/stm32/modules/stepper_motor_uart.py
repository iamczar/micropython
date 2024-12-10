from tmc2240 import TMC2240  # Assuming tmc2240.py provides this class
from tmc2240_settings import IHOLD_IRUN,CHOPCONF,Register
from simple_logger import SimpleLogger
#from event_bus import EventBus


class StepperMotorUART:
    #def __init__(self, tmc2240: TMC2240, event_bus: EventBus, logger: SimpleLogger, subscribe_topic: str, publish_topic: str = None):
    def __init__(self, tmc2240: TMC2240, logger: SimpleLogger, subscribe_topic: str, publish_topic: str = None):
        """
        Initializes the StepperMotorUART with the given parameters.

        :param tmc2240: An instance of the TMC2240 class to control the stepper motor.
        :param event_bus: The EventBus instance for subscribing to and publishing events.
        :param logger: An instance of SimpleLogger for logging.
        :param subscribe_topic: The topic to subscribe to for receiving stepper motor control commands.
        :param publish_topic: The topic to publish stepper motor status or responses to (optional).
        """
        self.tmc2240 = tmc2240
        #self.event_bus = event_bus
        self.logger = logger
        self.subscribe_topic = subscribe_topic
        self.publish_topic = publish_topic
        self.tmc_pump_driver_address_1 = 0x00
        self.tmc_pump_driver_address_2 = 0x07
        

        # Subscribe to the specified topic on the event bus
        #self.event_bus.subscribe(self.subscribe_topic, self.handle_event)

        # Initialize the TMC2240 for step/direction control
        self._initialize()

    def _initialize(self):
        """
        Initializes the TMC2240 stepper motor driver with the required settings.
        This function is private and is automatically called during object instantiation.
        """
        try:
            self.logger.info("Initializing TMC2240 stepper motor driver for step/direction control...")

            self.logger.info("Reading ihold_irun for both pumps......")
            pump_1_ihold_irun:IHOLD_IRUN = self.tmc2240.read_ihold_irun(self.tmc_pump_driver_address_1)
            pump_2_ihold_irun:IHOLD_IRUN = self.tmc2240.read_ihold_irun(self.tmc_pump_driver_address_2)
            
            if pump_1_ihold_irun is None:
                self.logger.error("Failed to read pump_1_ihold_irun register: No response from device")
                return
            
            if pump_2_ihold_irun is None:
                self.logger.error("Failed to read pump_2_ihold_irun register: No response from device")
                return
            
            self.logger.info("Setting IHOLD_IRUN")
            pump_1_ihold_irun.set_ihold(2)  
            pump_1_ihold_irun.set_irun(20)
            pump_2_ihold_irun.set_ihold(2)  
            pump_2_ihold_irun.set_irun(20)
            
            self.tmc2240.write_ihold_irun(self.tmc_pump_driver_address_1,pump_1_ihold_irun)
            self.tmc2240.write_ihold_irun(self.tmc_pump_driver_address_2,pump_2_ihold_irun)
            
            self.logger.info("Setting CHOPCONF")
            chopconf_pump_1:CHOPCONF = self.tmc2240.read_chopconf(self.tmc_pump_driver_address_1)
            chopconf_pump_2:CHOPCONF = self.tmc2240.read_chopconf(self.tmc_pump_driver_address_2)
            
            if chopconf_pump_1 is None:
                self.logger.error("Failed to read CHOPCONF register: No response from device")
                return
        
            if chopconf_pump_2 is None:
                self.logger.error("Failed to read CHOPCONF register: No response from device")
                return
            
            toff = 3
            hsttrt_tfd = 5
            hend_offset = 2
            tbl = 2
            tpfd = 4
            
            chopconf_pump_1.set_toff(toff)
            chopconf_pump_1.set_hstrt_tfd(hsttrt_tfd)
            chopconf_pump_1.set_hend_offset(hend_offset)
            chopconf_pump_1.set_tbl(tbl)
            chopconf_pump_1.set_tpfd(tpfd)
            chopconf_pump_1.set_mres(0x5)
            chopconf_pump_1.set_intpol(0x1)
            
            chopconf_pump_2.set_toff(toff)
            chopconf_pump_2.set_hstrt_tfd(hsttrt_tfd)
            chopconf_pump_2.set_hend_offset(hend_offset)
            chopconf_pump_2.set_tbl(tbl)
            chopconf_pump_2.set_tpfd(tpfd)
            chopconf_pump_2.set_mres(0x5)
            chopconf_pump_2.set_intpol(0x1)
            
            self.tmc2240.write_chopconf(self.tmc_pump_driver_address_1,chopconf_pump_1)
            self.tmc2240.write_chopconf(self.tmc_pump_driver_address_2,chopconf_pump_2)

            self.tmc2240.write_register(self.tmc_pump_driver_address_1, Register.DRV_CONF,0x3)
            self.tmc2240.write_register(self.tmc_pump_driver_address_2, Register.DRV_CONF,0x3)

            self.logger.info("TMC2240 initialization for step/direction control complete.")
        except Exception as e:
            self.logger.error(f"Failed to initialize TMC2240: {e}")

    # async def handle_event(self, data):
    #     """
    #     Handles incoming events from the subscribed topic.

    #     :param data: The data received from the subscribed topic.
    #     """
    #     # Placeholder for handling events
    #     # Currently, this function does nothing, but it will be used in the future
    #     pass

    def __del__(self):
        """
        Destructor to ensure the UART connection is properly closed when the object is deleted.
        """
        if self.tmc2240:
            if self.tmc2240.uart_wrapper:
                self.logger.info("Closing UART connection in __del__ method.")
                self.tmc2240.uart_wrapper.close()
            self.tmc2240 = None  # Help the garbage collector by nullifying the reference
        self.logger = None