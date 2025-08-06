import uos
import utime
import uasyncio as asyncio
import json
from simple_logger import SimpleLogger
from event_bus import EventBus
import array


class SensorDataIndex:
    STATEID = 0
    OXYMEASURED = 1
    PRESSUREMEASURED = 2
    FLOWMEASURED = 3
    TEMPMEASURED = 4
    CIRCPUMPSPEED = 5
    PRESSUREPUMPSPEED = 6
    PRESSUREPID = 7
    PRESSURESETPOINT = 8
    PRESSUREKP = 9
    PRESSUREKI = 10
    PRESSUREKD = 11
    OXYGENPID = 12
    OXYGENSETPOINT = 13
    OXYGENKP = 14
    OXYGENKI = 15
    OXYGENKD = 16
    OXYGENMEASURED1 = 17
    OXYGENMEASURED2 = 18
    OXYGENMEASURED3 = 19
    OXYGENMEASURED4 = 20


class DataLogger:
    def __init__(self, module_id: int, 
                 event_bus: EventBus, 
                 log_loop_frequency_hz: float, 
                 logger: SimpleLogger = None):
        self.module_id = module_id
        self.event_bus = event_bus
        self.logger = logger
        self.log_active = False
        self.filename = None
        self.sensor_data_array = array.array('f', [0.0] * 21)  # 'f' for float

        self.sensor_read_interval = 1 / log_loop_frequency_hz

        # Subscribe to sensor topics
        self.subscribe_to_topic("oxy-sen-1", self.handle_event_oxy1)
        self.subscribe_to_topic("oxy-sen-2", self.handle_event_oxy2)
        self.subscribe_to_topic("oxy-sen-3", self.handle_event_oxy3)
        self.subscribe_to_topic("tempflow-sen", self.handle_event_temp_flow)
        self.subscribe_to_topic("pressure-sen", self.handle_event_pressure)
        self.subscribe_to_topic("oxy-pump-01-status",self.handle_oxy_pump_status)
        self.subscribe_to_topic("press-pump-02-status",self.handle_press_pump_status)
        self.subscribe_to_topic("circ-flow-pid",self.handle_circ_flow_pid)
        self.subscribe_to_topic("pressure-pid",self.handle_press_pid)
               
        # Subscribe to the data-logger-actuator to start/stop logging
        self.subscribe_to_topic("data-log-cmd", self.handle_event_datalogger)

        if self.logger:
            self.logger.info("DataLogger initialized")

    def subscribe_to_topic(self, topic, handler=None):
        """Subscribe to a new topic with an optional specific handler function."""
        if handler:
            self.event_bus.subscribe(topic, handler)
            #if self.logger:
                #self.logger.info(f"Subscribed to topic: {topic}")

    def _get_timestamp_for_filename(self):
        """Generates a precise timestamp for the filename."""
        now = utime.localtime()
        microseconds = utime.ticks_us() % 1_000_000  # Get the microsecond part
        return "{:04}-{:02}-{:02} {:02}:{:02}:{:02}.{:06}".format(
            now[0], now[1], now[2], now[3], now[4], now[5], microseconds
        )

    async def logging_loop(self):
        """Asynchronous loop that periodically logs sensor data if logging is active."""
        while True:
            try:
                if self.log_active:
                    # Write sensor data to the file
                    self._write_to_file()
                    
                # Output sensor data directly to USB_VCP via print()
                self._output_sensor_data()
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in logging loop: {e}")

            await asyncio.sleep(self.sensor_read_interval)

    async def handle_event_datalogger(self, data):
        """Handles start/stop commands for logging."""
        try:
            # Only start logging if it's not already active
            if data == True and not self.log_active:
                self.log_active = True
                # if self.logger:
                #     self.logger.info("Logging session started.")
            # Stop logging if requested
            elif data == False and self.log_active:
                self.log_active = False
                self.close()
                # if self.logger:
                #     self.logger.info("Logging session stopped.")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in handle_event_datalogger: {e}")
        await asyncio.sleep(0)

    async def handle_event_oxy1(self, data):
        self.sensor_data_array[SensorDataIndex.OXYGENMEASURED1] = data
        await asyncio.sleep(0)

    async def handle_event_oxy2(self, data):
        self.sensor_data_array[SensorDataIndex.OXYGENMEASURED2] = data
        await asyncio.sleep(0)

    async def handle_event_oxy3(self, data):
        self.sensor_data_array[SensorDataIndex.OXYGENMEASURED3] = data
        await asyncio.sleep(0)

    async def handle_event_temp_flow(self, data):
        flow,temp = data
        self.sensor_data_array[SensorDataIndex.FLOWMEASURED] = flow
        self.sensor_data_array[SensorDataIndex.TEMPMEASURED] = temp
        # if self.logger:
        #     self.logger.debug(f"temp&flow data: {data}")
        await asyncio.sleep(0)

    async def handle_event_pressure(self, data):
        self.sensor_data_array[SensorDataIndex.PRESSUREMEASURED] = data
        # if self.logger:
        #     self.logger.debug(f"Pressure data: {data}")
        await asyncio.sleep(0)
        
    async def handle_oxy_pump_status(self,data):
        pump_id,target_frequency,direction = data
        self.sensor_data_array[SensorDataIndex.CIRCPUMPSPEED] = target_frequency
        # if self.logger:
        #     self.logger.debug(f"p1 speed: {data}")
        await asyncio.sleep(0)
        
    async def handle_press_pump_status(self,data):
        pump_id,target_frequency,direction = data
        self.sensor_data_array[SensorDataIndex.PRESSUREPUMPSPEED] = target_frequency
        # if self.logger:
        #     self.logger.debug(f"p2 speed: {data}")
        await asyncio.sleep(0)
        
    async def handle_press_pid(self,data):
        sp,kp,ki,kd = data
        self.sensor_data_array[SensorDataIndex.PRESSURESETPOINT] = sp
        self.sensor_data_array[SensorDataIndex.PRESSUREKP] = kp
        self.sensor_data_array[SensorDataIndex.PRESSUREKI] = ki
        self.sensor_data_array[SensorDataIndex.PRESSUREKD] = kd
        await asyncio.sleep(0)
    
    async def handle_circ_flow_pid(self,data):
        sp,kp,ki,kd = data
        self.sensor_data_array[SensorDataIndex.OXYGENSETPOINT] = sp
        self.sensor_data_array[SensorDataIndex.OXYGENKP] = kp
        self.sensor_data_array[SensorDataIndex.OXYGENKI] = ki
        self.sensor_data_array[SensorDataIndex.OXYGENKD] = kd
        await asyncio.sleep(0)
        
    def _write_to_file(self):
        """Write the sensor data directly to the CSV file and refresh the SD card."""
        try:

            if not self.filename:
                directory = '/sd/session_logs/'
                self.filename = f"{directory}{self.module_id}_data.csv"
            # Create log entry
            log_entry = ",".join([
                self._get_timestamp_for_filename(),  # Timestamp
                f"0",  # nullLeader
                f"{self.module_id}",  # Module ID
                f"1515",  # Command
                f"{self.sensor_data_array[SensorDataIndex.STATEID]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYMEASURED]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREMEASURED]}",
                f"{self.sensor_data_array[SensorDataIndex.FLOWMEASURED]}",
                f"{self.sensor_data_array[SensorDataIndex.TEMPMEASURED]}",
                f"{self.sensor_data_array[SensorDataIndex.CIRCPUMPSPEED]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREPUMPSPEED]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREPID]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSURESETPOINT]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREKP]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREKI]}",
                f"{self.sensor_data_array[SensorDataIndex.PRESSUREKD]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENPID]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENSETPOINT]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENKP]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENKI]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENKD]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENMEASURED1]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENMEASURED2]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENMEASURED3]}",
                f"{self.sensor_data_array[SensorDataIndex.OXYGENMEASURED4]}",
                f"0"  # nullTrailer
            ]) + '\n'

            # self.logger.debug(f"Writing log entry: {log_entry.strip()}")

            # Open the file in append mode and write the log entry
            with open(self.filename, 'a') as f:
                f.write(log_entry)
                f.flush()

            # Sync changes to ensure they are committed to the SD card
            uos.sync()
            #self.logger.info(f"Log entry written to: {self.filename}")

        except Exception as e:
            self.logger.error(f"Error writing to log file: {e}")

    def _output_sensor_data(self):
        """Output sensor data directly to USB_VCP via send_system_message in JSON format"""
        try:
            # Create JSON structure with named fields for better readability
            sensor_data = {
                "command": "sensor_data",
                "data": {
                    "state_id": self.sensor_data_array[SensorDataIndex.STATEID],
                    "oxy_measured": self.sensor_data_array[SensorDataIndex.OXYMEASURED],
                    "pressure_measured": self.sensor_data_array[SensorDataIndex.PRESSUREMEASURED],
                    "flow_measured": self.sensor_data_array[SensorDataIndex.FLOWMEASURED],
                    "temp_measured": self.sensor_data_array[SensorDataIndex.TEMPMEASURED],
                    "circ_pump_speed": self.sensor_data_array[SensorDataIndex.CIRCPUMPSPEED],
                    "pressure_pump_speed": self.sensor_data_array[SensorDataIndex.PRESSUREPUMPSPEED],
                    "pressure_pid": self.sensor_data_array[SensorDataIndex.PRESSUREPID],
                    "pressure_setpoint": self.sensor_data_array[SensorDataIndex.PRESSURESETPOINT],
                    "pressure_kp": self.sensor_data_array[SensorDataIndex.PRESSUREKP],
                    "pressure_ki": self.sensor_data_array[SensorDataIndex.PRESSUREKI],
                    "pressure_kd": self.sensor_data_array[SensorDataIndex.PRESSUREKD],
                    "oxygen_pid": self.sensor_data_array[SensorDataIndex.OXYGENPID],
                    "oxygen_setpoint": self.sensor_data_array[SensorDataIndex.OXYGENSETPOINT],
                    "oxygen_kp": self.sensor_data_array[SensorDataIndex.OXYGENKP],
                    "oxygen_ki": self.sensor_data_array[SensorDataIndex.OXYGENKI],
                    "oxygen_kd": self.sensor_data_array[SensorDataIndex.OXYGENKD],
                    "oxygen_measured_1": self.sensor_data_array[SensorDataIndex.OXYGENMEASURED1],
                    "oxygen_measured_2": self.sensor_data_array[SensorDataIndex.OXYGENMEASURED2],
                    "oxygen_measured_3": self.sensor_data_array[SensorDataIndex.OXYGENMEASURED3],
                    "oxygen_measured_4": self.sensor_data_array[SensorDataIndex.OXYGENMEASURED4]
                }
            }
            
            # Output to USB_VCP via send_system_message
            if self.logger:
                self.logger.send_system_message("data_logger", sensor_data)
            else:
                # Fallback to print() if no logger available
                print(json.dumps(sensor_data))
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error outputting sensor data: {e}")

    def close(self):
        """Ensure all data is written before shutting down."""
        if self.log_active:
            self.log_active = False
            uos.sync()  # Ensure data is committed to disk
            # if self.logger:
            #     self.logger.info("Log session closed.")
