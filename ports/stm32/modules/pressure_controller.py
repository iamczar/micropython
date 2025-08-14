# circflow if its -1 use PID then set point is oxySP

from pid import PID
from event_bus import EventBus
from simple_logger import SimpleLogger
import uasyncio as asyncio
from command_data_structure import PressurePumpCmds

class PressureFlowController:
    STATE_IDLE = 0
    STATE_DIRECT_CONTROL = 1
    STATE_PID = 2
    
    
    def __init__(self, event_bus: EventBus, 
                 logger:SimpleLogger, 
                 kp:float=1.0,
                 ki:float=1.0,
                 kd:float=1.0,
                 tube_bore = 1,
                 controller_loop_hz:int=10):
        self.event_bus = event_bus
        self.logger = logger
        self.controller_loop_intervals:int = 1/controller_loop_hz
        self.target_pressure_level:float = 1.0
        self.motor_direction = False
        self.desired_pressure_flow_ml_m:int = -1 # use PID as default > -1 means bypass PID
        self.motor_speed_hz:int = 1 # this is the variable that will store the output from the PID or the direct control
        self.pressure_mbar:int = 0
        self.pid = PID(Kp=kp,Ki=ki,Kd=kd, setpoint=1, output_limits=(-5000, 5000)) # motor frequency in hz
        self.logger = logger
        self.name = "PressFlowCtrl"
        self.state = PressureFlowController.STATE_IDLE
        self.pressure_pump_cmd = PressurePumpCmds()
        
        self.tube_bore_map = {
            1:170,# 1.6mm 170u per revolution
            2:320,# 2.4mm 320u per revolution
            3:495,# 3.2mm 495u per revolution
            4:655.7 # 4.8mm 830u per revolution (0.79*830)
        }
        
        self.tube_rate= self.tube_bore_map.get(tube_bore)
        self.subscribe_to_topic("pressure-sen", self.handle_event_pressure)
        self.subscribe_to_topic("pressure-pump-cmd", self.handle_pressure_pump_cmd)
        self.logger.info("pressflowctrl init")

    def subscribe_to_topic(self, topic, handler=None):
        """Subscribe to a topic to receive sensor data."""
        if handler:
            self.event_bus.subscribe(topic, handler)
            # if self.logger:
            #     self.logger.debug(f"Subscribed to topic: {topic}")

    async def handle_pressure_pump_cmd(self, pressure_pump_cmds):

        try:
            self.pressure_pump_cmd.unpack(pressure_pump_cmds)
        except Exception as e:
            self.logger.error(f"handle_pressure_pump_cmd:Unable to unpack{e}")
            return
        
        try:
            if self.pressure_pump_cmd.pressureFlowSpeed > -1:
                self.state = PressureFlowController.STATE_DIRECT_CONTROL
                msg = f"{self.name}: direct control enabled"
                self.logger.debug(msg)
            elif self.pressure_pump_cmd.pressureFlowSpeed == -1:
                self.state = PressureFlowController.STATE_PID
                msg = f"{self.name}: pid enabled"
                self.logger.debug(msg)
                
            #self.logger.debug(f"{self.name}:mot_dir:{self.pressure_pump_cmd.pump2dir}")
            #self.logger.debug(f"{self.name}:target_pressure_level:{self.pressure_pump_cmd.pressureSP}")
            self.pid.set_kp(self.pressure_pump_cmd.pressureKp)
            self.pid.set_ki(self.pressure_pump_cmd.pressureKi)
            self.pid.set_kd(self.pressure_pump_cmd.pressureKd)
            self.tube_rate = self.tube_bore_map.get(self.pressure_pump_cmd.tube_bore)
        except Exception as e:
            self.logger.error(f"handle_pressure_pump_cmd:{e}")

    async def handle_event_pressure(self, data):
        self.pressure_mbar = data
    
    async def controller_loop(self):
        """Main loop for receiving sensor data."""
        while True:
            if self.state == self.STATE_IDLE:
                self.logger.debug(f"{self.name}: Controller is idle.")
                await asyncio.sleep(self.controller_loop_intervals)
                continue
            
            if self.state == self.STATE_DIRECT_CONTROL:
                # Bypass PID and use direct control
                self.motor_speed_hz:int = int((8 * 200 * self.pressure_pump_cmd.pressureFlowSpeed)/(self.tube_rate * 60))
                self.logger.info(f"{self.name}:controller_loop:motor_speed_hz:{self.motor_speed_hz}:pressureFlowSpeed:{self.pressure_pump_cmd.pressureFlowSpeed}")
                
            elif self.state == self.STATE_PID:
                # Use PID control
                self.pid.set_setpoint(self.pressure_pump_cmd.pressureSP)
                throttle = self.pid.compute(self.pressure_mbar)
                self.motor_speed_hz = self.motor_speed_hz - throttle
                #self.logger.debug(f"controller_loop:pid enabled:target_oxy_lvl:{self.pressure_pump_cmd.pressureSP}:curent_oxy_percent_o2:{self.pressure_mbar}")

            pump_act_msg = (self.pressure_pump_cmd.pump2dir,
                            self.motor_speed_hz,
                            1)
            
            await self.event_bus.publish("press-pump-02-act", pump_act_msg)
            
            pressure_pid_msg = (self.pressure_pump_cmd.pressureSP,
                                self.pressure_pump_cmd.pressureKp,
                                self.pressure_pump_cmd.pressureKi,
                                self.pressure_pump_cmd.pressureKd)
            
            await self.event_bus.publish("pressure-pid", pressure_pid_msg)

            await asyncio.sleep(self.controller_loop_intervals)  # Adjust the loop frequency as needed

