from uart_wrapper_tmc import UARTWrapperTMC
from tmc2240_settings import ReadAccessReplyDatagram,Register,GCONF,IHOLD_IRUN,CHOPCONF
from simple_logger import SimpleLogger

class TMC2240:
    def __init__(self, uart_wrapper:UARTWrapperTMC, logger:SimpleLogger):
        self.uart_wrapper = uart_wrapper
        self.logger = logger
        
    def calc_crc(self,datagram):
        """Calculate CRC based on TMC2240 datasheet algorithm."""
        crc = 0  # Initialize CRC to 0
        datagramLength = len(datagram)
        
        for i in range(datagramLength):  # Iterate over all bytes (same as in C)
            currentByte = datagram[i]  # Get the current byte
            for _ in range(8):  # Process each bit in the byte
                if (crc >> 7) ^ (currentByte & 0x01):  # Check MSB of CRC and LSB of current byte
                    crc = (crc << 1) ^ 0x07  # XOR with the polynomial if MSB set
                else:
                    crc = crc << 1  # Just shift if MSB is not set
                crc &= 0xFF  # Ensure CRC remains within 8 bits
                currentByte >>= 1  # Shift the current byte to the right for the next bit
        
        return crc  # Return the final CRC value
    
    def pack_read_access_datagram(self, node_address, register):
        """Pack the read access datagram: Sync + Node Address + Register Address + CRC."""
        sync_byte = 0x05  # Sync byte
        datagram = [sync_byte, node_address, register]  # Sync + Node Address + Register Address
        crc = self.calc_crc(datagram)  # Calculate CRC
        datagram.append(crc)  # Append CRC to the datagram
        
        return datagram
        
    def read_register(self,node,register):
        datagram = self.pack_read_access_datagram(node, register)
        self.logger.debug(f"read_register:datagram:{[hex(byte) for byte in datagram]}")
        response = self.uart_wrapper.send_recv(datagram)
        
        if response:
            self.logger.debug(f"Received response for node {node}, register {register}: {response}")
            return response
        else:
            self.logger.debug(f"No response from node {node}, register {register}")
            return None

    def pack_write_access_datagram(self,node_address,register,data):
        # Convert node_address and register to single-byte values
        node_address = node_address & 0xFF
        register = register & 0xFF
        
        sync_byte = 0x05  # Sync byte
        write_operation = 0x01
        combined = (write_operation << 7) | register  # Combine write operation with register
        
        # Split the 32-bit integer data into 4 bytes
        datagram = [sync_byte, node_address, combined]
        datagram.append((data >> 24) & 0xFF)  # Data byte 3 (most significant)
        datagram.append((data >> 16) & 0xFF)  # Data byte 2
        datagram.append((data >> 8) & 0xFF)   # Data byte 1
        datagram.append(data & 0xFF)          # Data byte 0 (least significant)

        # Calculate CRC and append it
        crc = self.calc_crc(datagram)
        datagram.append(crc)
        self.logger.debug(f"pack_write_access_datagram: datagram : {[hex(byte) for byte in datagram]}")
        return datagram
    
    def write_register(self,node,register,value):
        datagram = self.pack_write_access_datagram(node, register, value)
        self.logger.debug(f"write_register:datagram:{datagram}")
        self.uart_wrapper.send(datagram)
      
    def read_gconf(self,node_address):
        response = self.read_register(node_address, Register.GCONF)
        read_access_reply_datagram = ReadAccessReplyDatagram(response)
        return GCONF(read_access_reply_datagram.data)

    def write_gconf(self,node_address, gconf:GCONF):
        self.write_register(node_address, Register.GCONF, gconf.gconf_value)
        
    def read_ihold_irun(self,node_address):
        response = self.read_register(node_address, Register.IHOLD_IRUN)
        read_access_reply_datagram = ReadAccessReplyDatagram(response)
        return IHOLD_IRUN(read_access_reply_datagram.data)

    def write_ihold_irun(self,node_address, ihold_irun:IHOLD_IRUN):
        self.write_register(node_address, Register.IHOLD_IRUN, ihold_irun.ihold_irun_value)
        
    def read_chopconf(self,node_address):
        response = self.read_register(node_address, Register.CHOPCONF)
        read_access_reply_datagram = ReadAccessReplyDatagram(response)
        return CHOPCONF(read_access_reply_datagram.data)

    def write_chopconf(self,node_address, chopconf):
        self.write_register(node_address, Register.CHOPCONF, chopconf.raw_value)



