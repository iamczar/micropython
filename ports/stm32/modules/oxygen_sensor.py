import uasyncio as asyncio
from pico_o2 import PicoO2
from event_bus import EventBus
from simple_logger import SimpleLogger
import gc

class OxygenSensor:
    def __init__(self, name,
                 pico_o2:PicoO2,
                 sensor_loop_frequency_hz:int,
                 publish_topic:str,event_bus:EventBus,
                 logger:SimpleLogger):
        self.name = name
        self.pico_o2 = pico_o2
        self.event_bus = event_bus
        self.publish_topic = publish_topic
        self.sensor_read_interval = 1/sensor_loop_frequency_hz
        self.logger = logger
        
    async def sensor_loop(self):
        while True:
            try:
                # Attempt to read the oxygen percentage
                percent_o2 = await self.read_percent_o2(channel=1)
                # self.logger.debug(f"{self.name}: percent_02: {percent_o2}")
                if percent_o2 is not None:
                    await self.event_bus.publish(self.publish_topic,(percent_o2/100))
                
            except Exception as e:
                # Log any error encountered during reading or publishing
                self.logger.error(f"Error in {self.name} sensor loop: {e}")

            # Wait for the next cycle
            gc.collect()
            await asyncio.sleep(self.sensor_read_interval)
        
        
    # def read_all_measurement(self):
    #     """
    #     Read all measurements from the PicoO2 sensor and return a parsed result as a dictionary.

    #     :return: A dictionary containing all available measurement data from the PicoO2 sensor.
    #     """
    #     # Trigger the measurement and get the PicoO2MeasurementResponse object
    #     response = self.pico_o2.trigger_measurement()

    #     # Return a dictionary with all the measurement data
    #     return {
    #         "command": response.get_command(),
    #         "channel": response.get_channel(),
    #         "sensor_types": response.get_sensor_types(),
    #         "status": response.get_status(),
    #         "dphi": response.get_dphi(),
    #         "oxygen_umolar": response.get_umolar(),
    #         "oxygen_mbar": response.get_mbar(),
    #         "air_saturation": response.get_airSat(),
    #         "temperature_sample": response.get_temp_sample(),
    #         "temperature_case": response.get_temp_case(),
    #         "signal_intensity": response.get_signal_intensity(),
    #         "ambient_light": response.get_ambient_light(),
    #         "pressure": response.get_pressure(),
    #         "humidity": response.get_humidity(),
    #         "resistor_temp": response.get_resistor_temp(),
    #         "percent_oxygen": response.get_percent_O2(),
    #         "reserved": response.get_reserved()
    #     }
        
    # def read_all_measurement_raw(self):
    #     response = self.pico_o2.trigger_measurement()
    #     return response
    
    # def read_temperature(self, channel=1):
    #     """
    #     Read the current temperature from the PicoO2 sensor.

    #     :param channel: The optical channel number (default is 1).
    #     :return: The current temperature in units of 10⁻³ °C, or None if an error occurs.
    #     """
    #     return self.pico_o2.read_temperature(channel)

    # def read_pressure(self, channel=1):
    #     """
    #     Read the current pressure from the PicoO2 sensor.

    #     :param channel: The optical channel number (default is 1).
    #     :return: The current pressure in units of 10⁻³ mbar, or None if an error occurs.
    #     """
    #     return self.pico_o2.read_pressure(channel)
    
    # def read_humidity(self, channel=1):
    #     """
    #     Read the current humidity from the PicoO2 sensor.

    #     :param channel: The optical channel number (default is 1).
    #     :return: The current humidity in units of 10⁻³ %RH, or None if an error occurs.
    #     """
    #     return self.pico_o2.read_humidity(channel)
    
    async def read_percent_o2(self, channel=1):
        """
        Read the current humidity from the PicoO2 sensor.

        :param channel: The optical channel number (default is 1).
        :return: The current humidity in units of 10⁻³ %RH, or None if an error occurs.
        """
        return self.pico_o2.read_percent_o2(channel=channel)
    
    # def calibrate_and_save_anoxic(self, channel=1):
    #     """
    #     Perform calibration in an anoxic environment and save the configuration.

    #     :param channel: The optical channel number (default is 1).
    #     :return: True if calibration and saving were successful, False otherwise.
    #     """
    #     return self.pico_o2.calibrate_and_save_anoxic(channel)

    # def calibrate_and_save_air(self, channel=1):
    #     """
    #     Perform calibration using the current environmental conditions and save the configuration.

    #     :param channel: The optical channel number (default is 1).
    #     :return: True if calibration and saving were successful, False otherwise.
    #     """
    #     return self.pico_o2.calibrate_and_save_air(channel)

    # def get_device_info(self):
    #     """
    #     Retrieve the device information from the PicoO2 sensor.

    #     :return: The device information as a PicoO2DeviceInfo object.
    #     """
    #     return self.pico_o2.get_device_info()

    # def get_unique_id(self):
    #     """
    #     Retrieve the unique ID of the PicoO2 sensor.

    #     :return: The unique ID as a string.
    #     """
    #     return self.pico_o2.get_unique_id()

    # def flash_status_led(self):
    #     """
    #     Flash the status LED on the PicoO2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     return self.pico_o2.flash_status_led()

    # def power_down(self):
    #     """
    #     Power down the PicoO2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     return self.pico_o2.power_down()

    # def power_up(self):
    #     """
    #     Power up the PicoO2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     return self.pico_o2.power_up()

    # def enter_deep_sleep(self):
    #     """
    #     Put the PicoO2 sensor into deep sleep mode.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     return self.pico_o2.enter_deep_sleep()

    # def reset_device(self):
    #     """
    #     Reset the PicoO2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     return self.pico_o2.reset_device()