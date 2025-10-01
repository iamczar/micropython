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
        # PID control messages from AlphaCommsManager
        self.subscribe_to_topic("pid-pressure-controller", self.handle_pid_cmd)
        self.logger.info("pressflowctrl init")

        # PID status heartbeat (enabled)
        try:
            import uasyncio as asyncio
            asyncio.create_task(self._pid_status_loop())
        except Exception:
            pass

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
            # Also publish desired pressure pump speed in a consistent unit across modes.
            # - In DIRECT_CONTROL, publish the commanded pressureFlowSpeed.
            # - In PID mode, derive the equivalent pressureFlowSpeed from motor_speed_hz using the inverse mapping.
            try:
                desired_speed = 0.0
                if self.state == self.STATE_DIRECT_CONTROL:
                    desired_speed = float(self.pressure_pump_cmd.pressureFlowSpeed)
                elif self.state == self.STATE_PID:
                    # pressureFlowSpeed = motor_speed_hz * (tube_rate * 60) / (8 * 200)
                    if self.tube_rate:
                        desired_speed = (float(self.motor_speed_hz) * (self.tube_rate * 60.0)) / (8.0 * 200.0)
                    else:
                        desired_speed = 0.0
                await self.event_bus.publish("pressure-flow-desired-speed", desired_speed)
            except Exception:
                pass

            await asyncio.sleep(self.controller_loop_intervals)  # Adjust the loop frequency as needed

    async def handle_pid_cmd(self, payload):
        try:
            # Normalize payload to dict
            import json as _json
            if isinstance(payload, (bytes, bytearray)):
                try:
                    payload = _json.loads(payload.decode())
                except Exception:
                    payload = {}
            elif isinstance(payload, str):
                try:
                    payload = _json.loads(payload)
                except Exception:
                    payload = {}
            t = str(payload.get("type", "")).lower() if isinstance(payload, dict) else ""
            if t == "pressure_pid":
                # Apply gains and desired pressure only (do not change mode/state here)
                self.pressure_pump_cmd.pressureSP = float(payload.get("desired_pressure", self.pressure_pump_cmd.pressureSP))
                self.pressure_pump_cmd.pressureKp = float(payload.get("kp", self.pressure_pump_cmd.pressureKp))
                self.pressure_pump_cmd.pressureKi = float(payload.get("ki", self.pressure_pump_cmd.pressureKi))
                self.pressure_pump_cmd.pressureKd = float(payload.get("kd", self.pressure_pump_cmd.pressureKd))
                # Immediately publish updated status
                self._publish_pid_status_once()
            elif t == "pressure_pid_enable":
                enabled = bool(payload.get("enabled", False)) if isinstance(payload, dict) else False
                self.pressure_pump_cmd.pressureFlowSpeed = -1 if enabled else 0
                self.state = PressureFlowController.STATE_PID if enabled else PressureFlowController.STATE_DIRECT_CONTROL
                self._publish_pid_status_once()
            # Getter removed; periodic/status-on-change covers UI
        except Exception as e:
            self.logger.error(f"PressureFlowController: handle_pid_cmd error: {e}")

    async def _pid_status_loop(self):
        """Periodically publish current PID configuration/status for pressure controller."""
        while True:
            try:
                self._publish_pid_status_once()
            except Exception:
                pass
            # Heartbeat interval ~1s
            try:
                import uasyncio as asyncio
                await asyncio.sleep(1.0)
            except Exception:
                pass

    def _publish_pid_status_once(self):
        try:
            mode_map = {
                PressureFlowController.STATE_IDLE: "IDLE",
                PressureFlowController.STATE_DIRECT_CONTROL: "DIRECT",
                PressureFlowController.STATE_PID: "PID",
            }
            payload = {
                "event": "pid_status",
                "controller": "pressure",
                "pid_enabled": bool(self.pressure_pump_cmd.pressureFlowSpeed == -1),
                "desired_pressure": float(self.pressure_pump_cmd.pressureSP),
                "kp": float(self.pressure_pump_cmd.pressureKp),
                "ki": float(self.pressure_pump_cmd.pressureKi),
                "kd": float(self.pressure_pump_cmd.pressureKd),
                "mode": mode_map.get(self.state, "IDLE"),
            }
            self.logger.send_system_message("pid_pressure", payload)
        except Exception:
            pass

