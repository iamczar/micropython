# circflow if its -1 use PID then set point is oxySP

from pid import PID
from event_bus import EventBus
from simple_logger import SimpleLogger
import uasyncio as asyncio
from command_data_structure import OxyPumpCmds

class CircFlowController:
    STATE_IDLE = 0
    STATE_DIRECT_CONTROL = 1
    STATE_PID = 2
    
    
    def __init__(self, event_bus: EventBus, 
                 logger:SimpleLogger, 
                 kp:float=1.0,
                 ki:float=1.0,
                 kd:float=1.0,
                 oxy_pid_sensor = 1,
                 tube_bore = 1,
                 controller_loop_hz:int=10):
        self.event_bus = event_bus
        self.logger = logger
        self.controller_loop_intervals:float = 1/controller_loop_hz
        self.target_oxygen_level:float = 1.0
        self.motor_direction = False
        self.desired_flow_ml_m:int = -1 # use PID as default > -1 means bypass PID
        self.motor_speed_hz:int = 1 # this is the variable that will store the output from the PID or the direct control
        self.oxy_1_percent_o2:int = 0
        self.pid = PID(Kp=kp,Ki=ki,Kd=kd, setpoint=1, output_limits=(-1000, 1000))
        self.logger = logger
        self.name = "CircFlowController"
        self.state = CircFlowController.STATE_IDLE
        self.oxy_pump_cmds = OxyPumpCmds()
        
        # Define the lookup table for oxy sensors
        oxy_sensor_topic_map = {
            1: "oxy-sen-1",
            2: "oxy-sen-2",
            3: "oxy-sen-3"
        }
        
        self.tube_bore_map = {
            1:170,# 1.6mm 170u per revolution
            2:320,# 2.4mm 320u per revolution
            3:495,# 3.2mm 495u per revolution
            4:655.7 # 4.8mm 830u per revolution (0.79*830)
        }
        
        self.tube_rate = self.tube_bore_map.get(tube_bore)
        self.logger.info(f"{self.name}:tube_bore:{tube_bore}:tube_rate:{self.tube_rate }")
        oxy_sensor_topic = oxy_sensor_topic_map.get(oxy_pid_sensor, "oxy-sen-1")  # Default to oxy-sen-1 if not found
        self.subscribe_to_topic(oxy_sensor_topic, self.handle_event_oxy)

        self.subscribe_to_topic("oxy-pump-cmds", self.handle_oxy_pump_cmds)
        self.logger.info("CircFlowController Initilised")

    def subscribe_to_topic(self, topic, handler=None):
        """Subscribe to a topic to receive sensor data."""
        if handler:
            self.event_bus.subscribe(topic, handler)
            # if self.logger:
            #     self.logger.info(f"Subscribed to topic: {topic}")

    async def handle_oxy_pump_cmds(self, oxy_pump_cmds):

        try:
            self.oxy_pump_cmds.unpack(oxy_pump_cmds)
        except Exception as e:
            self.logger.error(f"handle_oxy_pump_cmds:Unable to unpack{e}")
            return
        
        try:
            if self.oxy_pump_cmds.circFlowSpeed > -1:
                self.state = CircFlowController.STATE_DIRECT_CONTROL
                # self.logger.debug(f"{self.name}: dc enabled")
            elif self.oxy_pump_cmds.circFlowSpeed == -1:
                self.state = CircFlowController.STATE_PID
                # self.logger.debug(f"{self.name}: pid enabled")

            # self.logger.debug(f"{self.name}:mot_dir:{self.oxy_pump_cmds.pump1dir}")
            # self.logger.debug(f"{self.name}:target_oxy_lvl:{self.oxy_pump_cmds.oxySP}")
            self.pid.set_kp(self.oxy_pump_cmds.oxyKp)
            self.pid.set_ki(self.oxy_pump_cmds.oxyKi)
            self.pid.set_kd(self.oxy_pump_cmds.oxyKd)
            self.tube_rate = self.tube_bore_map.get(self.oxy_pump_cmds.tube_bore)
        except Exception as e:
            self.logger.error(f"handle_serial_cmd_parser_event:{e}")
    
    async def handle_event_oxy(self, data):
        self.oxy_1_percent_o2 = data
    
    async def controller_loop(self):
        """Main loop for receiving sensor data."""
        while True:
    
            if self.state == self.STATE_IDLE:
                # self.logger.debug(f"{self.name}: Controller is idle.")
                await asyncio.sleep(self.controller_loop_intervals)
                continue
            
            if self.state == self.STATE_DIRECT_CONTROL:
                # Bypass PID and use direct control
                self.motor_speed_hz:int = int((8 * 200 * self.oxy_pump_cmds.circFlowSpeed)/(self.tube_rate * 60))
                self.logger.info(f"{self.name}:controller_loop:motor_speed_hz:{self.motor_speed_hz}:circFlowSpeed:{self.oxy_pump_cmds.circFlowSpeed}")
                
            elif self.state == self.STATE_PID:
                # Use PID control
                self.pid.set_setpoint(self.oxy_pump_cmds.oxySP)
                throttle = self.pid.compute(self.oxy_1_percent_o2)
                self.motor_speed_hz = self.motor_speed_hz + throttle
                #self.logger.debug(f"controller_loop:pid enabled:target_oxy_lvl:{self.oxy_pump_cmds.oxySP}:curent_oxy_percent_o2:{self.oxy_1_percent_o2}")

            pump_1_actuator_msg = (self.oxy_pump_cmds.pump1dir,
                                      self.motor_speed_hz,
                                      self.oxy_pump_cmds.pump_2_speed_ratio)
            
            await self.event_bus.publish("oxy-pump-01-act", pump_1_actuator_msg)
            
            circ_flow_pid_msg = (self.oxy_pump_cmds.oxySP,
                                self.oxy_pump_cmds.oxyKp,
                                self.oxy_pump_cmds.oxyKi,
                                self.oxy_pump_cmds.oxyKd)
            
            await self.event_bus.publish("circ-flow-pid", circ_flow_pid_msg)

            await asyncio.sleep(self.controller_loop_intervals)  # Adjust the loop frequency as needed

