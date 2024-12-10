from uart_wrapper import UARTWrapper
from pico_o2_settings import PicoO2MeasurementResponse, PicoO2Command, PicoO2Error
#from sensors.pico_o2_settings import PicoO2DeviceInfo

class PicoO2:
    def __init__(self, uart_wrapper:UARTWrapper, logger=None):
        """
        Initialize the PicoO2 class with a UARTWrapper instance and an optional logger.

        :param uart_wrapper: Instance of UARTWrapper for communication.
        :param logger: Optional logger for logging messages.
        """
        self.uart = uart_wrapper
        self.logger = logger
        self.power_up()

    def _send_command(self, command):
        """
        Send a command to the Pico-O2 sensor.

        :param command: The full command string to send.
        :return: The response from the sensor.
        """
        try:
            if self.logger:
                self.logger.debug(f"Sending command: {command}")
            
            self.uart.clear_buffer()  # Clear any stale data in the UART buffer
            self.uart.send(command + '\r\n')  # Send the command with a carriage return
            # Await the response and decode it if needed
            response = self.uart.recv(280)  # Read the response (adjust nbytes as needed)

            
            if isinstance(response, bytes):
                response = response.decode('utf-8')  # Decode the response if it's in bytes

            if self.logger:
                self.logger.debug(f"Received response: {response}")
            
            return response
        except Exception as e:
            self.logger.debug(f"Failed to send: {response}")
            return "None"

    def trigger_measurement(self, channel:int=1)->PicoO2MeasurementResponse:
        sensor_types = 47
        command = f"{PicoO2Command.TRIGGER_MEASUREMENT} {channel} {sensor_types}"
        response = self._send_command(command).strip()

        # Check if the response is an error
        if response.startswith("#ERRO"):
            error_code = response.replace("#ERRO", "").strip()  # Extract the error code
            raise PicoO2Error(error_code)
    
        # Parse the response using PicoO2MeasurementResponse class
        return PicoO2MeasurementResponse(response)

    # def read_temperature(self, channel=1):
    #     """
    #     Read the current temperature from the Pico-O2 sensor.

    #     :param channel: The optical channel number (usually 1).
    #     :return: The current temperature in units of 10⁻³ °C, or None if an error occurs.
    #     :raises PicoO2Error: If an error occurs during measurement.
    #     """
    #     try:
    #         response = self.trigger_measurement(channel)
    #         return response.get_temp_sample()
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to read temperature: {e}")
    #         # Depending on your needs, you can either return None, raise the error, or handle it differently.
    #         return None

    # def read_pressure(self, channel=1):
    #     """
    #     Read the current pressure from the Pico-O2 sensor.

    #     :param channel: The optical channel number (usually 1).
    #     :return: The current pressure in units of 10⁻³ mbar, or None if an error occurs.
    #     :raises PicoO2Error: If an error occurs during measurement.
    #     """
    #     try:
    #         response = self.trigger_measurement(channel)
    #         return response.get_pressure()
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to read pressure: {e}")
    #         # Depending on your needs, you can either return None, raise the error, or handle it differently.
    #         return None

    # def read_humidity(self, channel=1):
    #     """
    #     Read the current humidity from the Pico-O2 sensor.

    #     :param channel: The optical channel number (usually 1).
    #     :return: The current humidity in units of 10⁻³ %RH, or None if an error occurs.
    #     :raises PicoO2Error: If an error occurs during measurement.
    #     """
    #     try:
    #         response = self.trigger_measurement(channel)
    #         return response.get_humidity()
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to read humidity: {e}")
    #         # Depending on your needs, you can either return None, raise the error, or handle it differently.
    #         return None
        
    def read_percent_o2(self, channel=1):
        """
        Read the current humidity from the Pico-O2 sensor.

        :param channel: The optical channel number (usually 1).
        :return: The current humidity in units of 10⁻³ %RH, or None if an error occurs.
        :raises PicoO2Error: If an error occurs during measurement.
        """
        try:
            response = self.trigger_measurement(channel)
            return response.get_percent_O2()
        except PicoO2Error as e:
            if self.logger:
                self.logger.error(f"Failed to read percent 02: {e}")
            # Depending on your needs, you can either return None, raise the error, or handle it differently.
            return None

    # def _calibrate_air(self, channel, temperature, pressure, humidity):
    #     """
    #     Calibrate the Pico-O2 sensor at ambient air.

    #     :param channel: The optical channel number (usually 1).
    #     :param temperature: The temperature of the calibration environment in units of 10⁻³ °C.
    #     :param pressure: Ambient air pressure in units of 10⁻³ mbar.
    #     :param humidity: Relative humidity in units of 10⁻³ %RH.
    #     :return: True if calibration was successful, False otherwise.
    #     :raises PicoO2Error: If an error occurs during the calibration command.
    #     """
    #     command = f"{PicoO2Command.CALIBRATE_AIR} {channel} {temperature} {pressure} {humidity}"
    #     try:
    #         response = self._send_command(command)
    #         # If no exception is raised, and the response isn't an error, consider it successful
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Calibration error: {e}")
    #         return False

    # def _calibrate_anoxic(self, channel, temperature):
    #     """
    #     Calibrate the Pico-O2 sensor in an anoxic environment (0% O2).

    #     :param channel: The optical channel number.
    #     :param temperature: The temperature of the calibration environment.
    #     :return: True if calibration was successful, False otherwise.
    #     :raises PicoO2Error: If an error occurs during the calibration command.
    #     """
    #     command = f"{PicoO2Command.CALIBRATE_ANOXIC} {channel} {temperature}"
    #     try:
    #         response = self._send_command(command)
    #         # If no exception is raised, and the response isn't an error, consider it successful
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Calibration error: {e}")
    #         return False

    # def _save_configuration(self, channel: int = 1) -> bool:
    #     """
    #     Save the current configuration to the Pico-O2's flash memory.

    #     :param channel: The optical channel number.
    #     :return: True if the configuration was saved successfully, False otherwise.
    #     :raises PicoO2Error: If an error occurs during the save configuration command.
    #     """
    #     command = f"{PicoO2Command.SAVE_CONFIGURATION} {channel}"
    #     try:
    #         response = self._send_command(command)
    #         # If no exception is raised, and the response isn't an error, consider it successful
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Save configuration error: {e}")
    #         return False
    
    # def calibrate_and_save_anoxic(self,channel:int=1) -> bool:
    #     """
    #     Perform calibration in an anoxic environment and save the configuration.

    #     :param channel: The optical channel number (usually 1).
    #     :return: True if calibration and saving were successful, False otherwise.
    #     """
    #     try:
    #         current_temperature = self.read_temperature(channel)
    #         if current_temperature is None:
    #             return False
            
    #         if not self._calibrate_anoxic(channel, current_temperature):
    #             return False
            
    #         if not self._save_configuration(channel):
    #             return False
            
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Calibration and save (anoxic) failed: {e}")
    #         return False
    
    # def calibrate_and_save_air(self, channel:int=1) -> bool:
    #     """
    #     Perform calibration using the current environmental conditions and save the configuration.

    #     :param channel: The optical channel number (usually 1).
    #     :return: True if calibration and saving were successful, False otherwise.
    #     """
    #     try:
    #         response = self.trigger_measurement(channel)
    #         current_temperature = response.get_temp_sample()
    #         current_pressure = response.get_pressure()
    #         current_humidity = response.get_humidity()

    #         if not self._calibrate_air(channel, current_temperature, current_pressure, current_humidity):
    #             return False
            
    #         if not self._save_configuration(channel):
    #             return False
            
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Calibration and save (air) failed: {e}")
    #         return False

    # def get_device_info(self) -> PicoO2DeviceInfo:
    #     """
    #     Retrieve the device information.

    #     :return: The device information as a response from the sensor.
    #     """
    #     command = PicoO2Command.GET_DEVICE_INFO
    #     try:
    #         response = self._send_command(command)
    #         return PicoO2DeviceInfo(response)
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to get device info: {e}")
    #         return None

    # def get_unique_id(self) -> str:
    #     """
    #     Retrieve the unique ID of the Pico-O2 sensor and return it as a string.

    #     :return: The unique ID as a string, or None if an error occurs.
    #     """
    #     command = PicoO2Command.GET_UNIQUE_ID
    #     try:
    #         response = self._send_command(command).strip()

    #         if response.startswith("#IDNR"):
    #             unique_id_str = response.replace("#IDNR", "").strip()
    #             return unique_id_str
    #         else:
    #             if self.logger:
    #                 self.logger.error(f"Unexpected response format: {response}")
    #             return None
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to get unique ID: {e}")
    #         return None

    # def flash_status_led(self) -> bool:
    #     """
    #     Flash the status LED on the Pico-O2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     command = PicoO2Command.FLASH_STATUS_LED
    #     try:
    #         self._send_command(command)
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to flash status LED: {e}")
    #         return False

    # def power_down(self) -> bool:
    #     """
    #     Power down the sensor circuits of the Pico-O2.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     command = PicoO2Command.POWER_DOWN
    #     try:
    #         self._send_command(command)
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to power down: {e}")
    #         return False


    def power_up(self) -> bool:
        """
        Power up the sensor circuits of the Pico-O2.

        :return: True if the command was successful, False otherwise.
        """
        command = PicoO2Command.POWER_UP
        try:
            self._send_command(command)
            return True
        except PicoO2Error as e:
            if self.logger:
                self.logger.error(f"Failed to power up: {e}")
            return False

    # def enter_deep_sleep(self) -> bool:
    #     """
    #     Put the Pico-O2 sensor into deep sleep mode.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     command = PicoO2Command.ENTER_DEEP_SLEEP
    #     try:
    #         self._send_command(command)
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to enter deep sleep: {e}")
    #         return False

    # def reset_device(self) -> bool:
    #     """
    #     Reset the Pico-O2 sensor.

    #     :return: True if the command was successful, False otherwise.
    #     """
    #     command = PicoO2Command.RESET_DEVICE
    #     try:
    #         self._send_command(command)
    #         return True
    #     except PicoO2Error as e:
    #         if self.logger:
    #             self.logger.error(f"Failed to reset device: {e}")
    #         return False

    # def read_user_memory(self, address, length):
    #     """
    #     Read data from the user memory of the Pico-O2 sensor.

    #     :param address: The starting address to read from.
    #     :param length: The number of registers to read.
    #     :return: The response from the sensor.
    #     """
    #     command = f"#RDUM {address} {length}"
    #     return self.send_command(command)

    # def write_user_memory(self, address, data):
    #     """
    #     Write data to the user memory of the Pico-O2 sensor.

    #     :param address: The starting address to write to.
    #     :param data: The data to write.
    #     :return: The response from the sensor.
    #     """
    #     command = f"#WRUM {address} {data}"
    #     return self.send_command(command)

