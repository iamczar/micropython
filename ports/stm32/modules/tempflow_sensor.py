import uasyncio as asyncio
import time
from slf3c_1300f import SLF3C1300F
from event_bus import EventBus



class TempFlowSensor:
    def __init__(self, slf3c1300f: SLF3C1300F, event_bus: EventBus, logger, loop_hz:int):
        self.slf3c1300f = slf3c1300f
        self.event_bus = event_bus
        self.logger = logger
        self.loop_intervals = 1/loop_hz
        self._is_running = False

    async def sensor_loop(self):
        """Main loop for reading and publishing sensor data."""
        self._is_running = True
        #self.logger.debug("Start measurement")
        # self.slf3c1300f.start_measurement(Slf31c1300fMedium.water)
        self.slf3c1300f.start_measurement()
        time.sleep(1)
        try:
            while self._is_running:
                #self.logger.debug(f"attempting to read")
                #flow, temp, flags = self.slf3c1300f.read_data()
                flow, temp = self.slf3c1300f.read_data()
                
                data = (flow,temp)
                #self.logger.debug(f"tempfllow pub: {data}")
                await self.event_bus.publish("tempflow-sen", data)
                await asyncio.sleep(self.loop_intervals)  # Adjust the interval as needed

        except Exception as e:
            self.logger.error(f"TempFlowSensor: {e}")
            # self.slf3c1300f.stop_measurement()

    def stop(self):
        """Stop the sensor loop."""
        self._is_running = False
        # self.slf3c1300f.stop_measurement()
