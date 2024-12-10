class PicoO2Command:
    TRIGGER_MEASUREMENT = "MEA"
    # CALIBRATE_AIR = "CHI"
    # CALIBRATE_ANOXIC = "CLO"
    # SAVE_CONFIGURATION = "SVS"
    # GET_DEVICE_INFO = "#VERS"
    # GET_UNIQUE_ID = "#IDNR"
    # FLASH_STATUS_LED = "#LOGO"
    # POWER_DOWN = "#PDWN"
    POWER_UP = "#PWUP"
    # ENTER_DEEP_SLEEP = "#STOP"
    # RESET_DEVICE = "#RSET"
    # READ_USER_MEMORY = "#RDUM"
    # WRITE_USER_MEMORY = "#WRUM"
    # HANDLE_ERROR = "#ERRO"

    # @staticmethod
    # def all_commands():
    #     """Return a list of all command values."""
    #     return [
    #         PicoO2Command.TRIGGER_MEASUREMENT,
    #         PicoO2Command.CALIBRATE_AIR,
    #         PicoO2Command.CALIBRATE_ANOXIC,
    #         PicoO2Command.SAVE_CONFIGURATION,
    #         PicoO2Command.GET_DEVICE_INFO,
    #         PicoO2Command.GET_UNIQUE_ID,
    #         PicoO2Command.FLASH_STATUS_LED,
    #         PicoO2Command.POWER_DOWN,
    #         PicoO2Command.POWER_UP,
    #         PicoO2Command.ENTER_DEEP_SLEEP,
    #         PicoO2Command.RESET_DEVICE,
    #         PicoO2Command.READ_USER_MEMORY,
    #         PicoO2Command.WRITE_USER_MEMORY,
    #         PicoO2Command.HANDLE_ERROR,
    #     ]

    # def __str__(self):
    #     """Return a string representation of the command class."""
    #     return f"PicoO2Command({', '.join(self.all_commands())})"
    
class PicoO2MeasurementResponse:
    def __init__(self, response):
        fields = response.split()
        # self.command = fields[0]
        # self.channel = int(fields[1])
        # self.sensor_types = int(fields[2])
        # self.status = int(fields[3])
        # self.dphi = int(fields[4])
        # self.umolar = int(fields[5])
        # self.mbar = int(fields[6])
        # self.airSat = int(fields[7])
        # self.tempSample = int(fields[8])
        # self.tempCase = int(fields[9])
        # self.signalIntensity = int(fields[10])
        # self.ambientLight = int(fields[11])
        # self.pressure = int(fields[12])
        # self.humidity = int(fields[13])
        # self.resistorTemp = int(fields[14])
        self.percentO2 = int(fields[15])
        # self.reserved = fields[16:]

    # def is_valid(self):
    #     """
    #     Check if the response is valid by evaluating the status field.
    #     A status of 0 indicates no errors or warnings.
    #     """
    #     return self.status == 0
    
    # # Getter methods for each attribute
    # def get_command(self):
    #     return self.command

    # def get_channel(self):
    #     return self.channel

    # def get_sensor_types(self):
    #     return self.sensor_types

    # def get_status(self):
    #     return self.status

    # def get_dphi(self):
    #     return self.dphi

    # def get_umolar(self):
    #     return self.umolar

    # def get_mbar(self):
    #     return self.mbar

    # def get_airSat(self):
    #     return self.airSat

    # def get_temp_sample(self):
    #     return self.tempSample

    # def get_temp_case(self):
    #     return self.tempCase

    # def get_signal_intensity(self):
    #     return self.signalIntensity

    # def get_ambient_light(self):
    #     return self.ambientLight

    # def get_pressure(self):
    #     return self.pressure

    # def get_humidity(self):
    #     return self.humidity

    # def get_resistor_temp(self):
    #     return self.resistorTemp

    def get_percent_O2(self):
        return self.percentO2

    # def get_reserved(self):
    #     return self.reserved
    
    # def __repr__(self):
    #     return ("PicoO2Response(command={}, channel={}, sensor_types={}, status={}, "
    #             "dphi={}, umolar={}, mbar={}, airSat={}, tempSample={}, tempCase={}, "
    #             "signalIntensity={}, ambientLight={}, pressure={}, humidity={}, "
    #             "resistorTemp={}, percentO2={}, reserved={})"
    #             .format(self.command, self.channel, self.sensor_types, self.status, 
    #                     self.dphi, self.umolar, self.mbar, self.airSat, 
    #                     self.tempSample, self.tempCase, self.signalIntensity, 
    #                     self.ambientLight, self.pressure, self.humidity, 
    #                     self.resistorTemp, self.percentO2, self.reserved))
        
class PicoO2DeviceInfo:
    def __init__(self, response):
        fields = response.split()
        self.firmware_version = fields[0]  # Assuming this is the firmware version
        self.hardware_version = fields[1]  # Assuming this is the hardware version
        self.serial_number = fields[2]     # Assuming this is the serial number
        self.additional_info = fields[3:]  # Any other additional information provided

    def __repr__(self):
        return ("PicoO2DeviceInfo(firmware_version={}, hardware_version={}, "
                "serial_number={}, additional_info={})"
                .format(self.firmware_version, self.hardware_version, 
                        self.serial_number, self.additional_info))

    # Add getter methods if needed
    def get_firmware_version(self):
        return self.firmware_version

    def get_hardware_version(self):
        return self.hardware_version

    def get_serial_number(self):
        return self.serial_number

    def get_additional_info(self):
        return self.additional_info
    
class PicoO2Error(Exception):
    """Custom exception class for handling Pico-O2 sensor errors."""

    ERROR_CODES = {
        "-1": "General: A non-specific error occurred.",
        "-2": "Channel: The requested optical channel does not exist.",
        "-11": "Memory Access: Memory access violation either caused by a non-existing requested register, or by an out of range address of the requested value.",
        "-12": "Memory Lock: The requested memory is locked (system register) and a write access was requested.",
        "-13": "Memory Flash: An error occurred while saving the registers permanently. The SVS request should be repeated.",
        "-14": "Memory Erase: An error occurred while erasing the permanent memory region for the registers. The SVS request should be repeated.",
        "-15": "Memory Inconsistent: The registers in RAM are inconsistent with the permanently stored registers after processing SVS. The SVS request should be repeated.",
        "-21": "UART Parse: An error occurred while parsing the command string. The last command should be repeated.",
        "-22": "UART Rx: The command string was not received correctly (e.g., device was not ready, last request was not terminated correctly). Repeat the last command.",
        "-23": "UART Header: The command header could not be interpreted correctly (must contain only characters from A-Z). Repeat the last command.",
        "-24": "UART Overflow: The command string could not be processed fast enough to prevent an overflow of the internal receiving buffer.",
        "-25": "UART Baudrate: The requested baudrate is not supported. No baudrate change took place.",
        "-26": "UART Request: The command header does not match any of the supported commands.",
        "-27": "UART Start Rx: The device was waiting for incoming data; however, the next event was not triggered by receiving a command.",
        "-28": "UART Range: One or more parameters of the command are out of range.",
        "-30": "I2C Transfer: There was an error transferring data on the I2C bus.",
        "-40": "Temp Ext: The communication with the sample temperature sensor was not successful.",
        "-41": "Periphery No Power: The power supply of the device periphery (sensors, SD card) is not switched on."
    }

    def __init__(self, error_code: str):
        self.error_code = error_code
        if error_code in self.ERROR_CODES:
            self.error_message = self.ERROR_CODES[error_code]
        else:
            self.error_message = f"Unknown error code: {error_code}"
        super().__init__(f"Error {error_code}: {self.error_message}")
