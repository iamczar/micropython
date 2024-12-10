# /sensors/slf3c_1300f.py
from i2c_wrapper import I2CWrapper

class Slf31c1300fCommands:
    START_MEASUREMENT_H2O = b'\x36\x08'
    # START_MEASUREMENT_IPA = b'\x36\x15'
    # STOP_MEASUREMENT = b'\x3F\xF9'
    # SOFT_RESET = b'\x00\x06'
    # READ_PRODUCT_ID = b'\x36\x7C\xE1\x02'
    
# class Slf31c1300fMedium:
#     water = 0
#     ipa = 1
    
# class Slf31c1300ScaleFactor:
#     FLOW = 500
#     TEMP = 200


class SLF3C1300F:
    def __init__(self, i2c_wrapper:I2CWrapper,logger=None):
        self.i2c_wrapper = i2c_wrapper
        self.logger = logger

    # def start_measurement(self, medium:Slf31c1300fMedium = Slf31c1300fMedium.water):
    #     """Start continuous measurement for water or IPA."""
    #     if Slf31c1300fMedium.water == medium:
    #         self.i2c_wrapper.send(Slf31c1300fCommands.START_MEASUREMENT_H2O)
    #     elif Slf31c1300fMedium.ipa == medium:
    #         self.i2c_wrapper.send(Slf31c1300fCommands.START_MEASUREMENT_IPA)
    #     else:
    #         raise ValueError("Invalid medium. Use 'water' or 'ipa'.")
        
        
    def start_measurement(self):
        self.i2c_wrapper.send(Slf31c1300fCommands.START_MEASUREMENT_H2O)

    # def stop_measurement(self):
    #     """Stop continuous measurement."""
    #     self.i2c_wrapper.send(Slf31c1300fCommands.STOP_MEASUREMENT)
        
    # def soft_reset(self):
    #     """Perform a soft reset of the sensor."""
    #     self.i2c_wrapper.send(Slf31c1300fCommands.SOFT_RESET)      
        
    # def read_product_id(self):
    #     """Read the product ID and serial number from the sensor."""
    #     self.i2c_wrapper.send(Slf31c1300fCommands.READ_PRODUCT_ID[:2])
    #     self.i2c_wrapper.send(Slf31c1300fCommands.READ_PRODUCT_ID[2:])
    #     data = self.i2c_wrapper.recv(18)
    #     product_number = int.from_bytes(data[0:4], 'big')
    #     serial_number = int.from_bytes(data[4:12], 'big')
    #     return product_number, serial_number
    
    def read_data(self):
        
        try:
            """Read the current flow rate, temperature, and signaling flags."""
            data = self.i2c_wrapper.recv(9)  # Reading 3 words (6 bytes) + 3 CRC bytes
            
            for i in range(0, len(data), 3):
                if not self.check_crc(data[i:i+2], data[i+2]):
                    raise ValueError("CRC check failed for data chunk.")
            
            flow_raw = int.from_bytes(data[0:2], 'big')
            temp_raw = int.from_bytes(data[3:5], 'big')
            # flags = int.from_bytes(data[6:8], 'big')

            flow_rate = flow_raw / 500
            temperature = temp_raw / 200
            
            # flow_rate = flow_raw / Slf31c1300ScaleFactor.FLOW
            # temperature = temp_raw / Slf31c1300ScaleFactor.TEMP

            #return flow_rate, temperature, flags
            return flow_rate, temperature
        except Exception as e:
            self.logger.error(f"slf:read_date:error{e}")
    
    # def get_status_flags(self, flags):
    #     """Interpret the status flags."""
    #     air_in_line = bool(flags & 0x01)
    #     high_flow = bool((flags >> 1) & 0x01)
    #     smoothing_active = bool((flags >> 5) & 0x01)

    #     return {
    #         "air_in_line": air_in_line,
    #         "high_flow": high_flow,
    #         "smoothing_active": smoothing_active
    #     }

    def check_crc(self, data, crc):
        crc_calc = 0xFF
        for byte in data:
            crc_calc ^= byte
            for _ in range(8):
                if crc_calc & 0x80:
                    crc_calc = (crc_calc << 1) ^ 0x31
                else:
                    crc_calc <<= 1
            crc_calc &= 0xFF
        return crc_calc == crc
