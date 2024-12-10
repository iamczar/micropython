import struct

class WriteAccessDatagram:
    def __init__(self, node_address):
        self.node_address = node_address
        
    def calc_crc(datagram):
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
    
    def pack_write_datagram(self, register_address, value):
        """Pack the write access datagram for a specific register address and value."""
        # 1. Sync byte
        sync_byte = 0x05

        # 2. RW + Register Address (RW = 1 for write, combine with 7-bit register address)
        rw_register = (1 << 7) | register_address

        # 3. Data (convert the value to 4 bytes, big-endian)
        data_bytes = value.to_bytes(4, 'big')

        # 4. Create the datagram (sync byte + node address + RW + register + data)
        datagram = bytearray([sync_byte, self.node_address, rw_register]) + data_bytes

        # 5. Calculate and append CRC
        crc_value = self.calculate_crc(datagram)
        datagram.append(crc_value)

        return datagram
    
class  ReadAccessReplyDatagram:
    
    def __init__(self, response):
        self.response = response
        self.sync_reserved = None
        self.node_address = 0
        self.rw_register_addr = 0
        self.data = 0
        self.crc = 0
        self.unpack()
        
    def unpack(self):
        """Unpack the response into sync_reserved, node_address, rw_register_addr, data, and crc."""
        if len(self.response) != 8:
            raise ValueError("Invalid response length, expected 8 bytes")

        # Unpack the first three bytes: sync_reserved, node_address, rw_register_addr
        self.sync_reserved, self.node_address, self.rw_register_addr = struct.unpack('BBB', self.response[:3])
        
        # Unpack the next four bytes as a 32-bit integer (big-endian) for data
        self.data = struct.unpack('>I', self.response[3:7])[0]
        
        # Unpack the last byte for crc
        self.crc = struct.unpack('B', self.response[7:])[0]

class Register:
    GCONF = 0x00
    IHOLD_IRUN = 0x10
    CHOPCONF = 0x6C
    DRV_CONF = 0x0A


class GCONF:
    # Bit field positions
    DIRECT_MODE = 16
    STOP_ENABLE = 15
    SMALL_HYSTERESIS = 14
    DIAG1_PUSHPULL = 13
    DIAG0_PUSHPULL = 12
    DIAG1_ONSTATE = 10
    DIAG1_INDEX = 9
    DIAG1_STALL = 8
    DIAG0_STALL = 7
    DIAG0_OTPW = 6
    DIAG0_ERROR = 5
    SHAFT = 4
    MULTISTEP_FILT = 3
    EN_PWM_MODE = 2
    FAST_STANDSTILL = 1

    def __init__(self, gconf_value=0):
        """Initialize with a default GCONF value (0 if not specified)."""
        self.gconf_value = gconf_value

    def set_bit(self, bit_position):
        """Set a specific bit to 1."""
        self.gconf_value |= (1 << bit_position)

    def clear_bit(self, bit_position):
        """Clear a specific bit (set to 0)."""
        self.gconf_value &= ~(1 << bit_position)

    def get_bit(self, bit_position):
        """Get the value of a specific bit (1 or 0)."""
        return (self.gconf_value >> bit_position) & 1

    # DIRECT_MODE (bit 16)
    def set_direct_mode(self, enable):
        if enable:
            self.set_bit(GCONF.DIRECT_MODE)
        else:
            self.clear_bit(GCONF.DIRECT_MODE)

    def get_direct_mode(self):
        return self.get_bit(GCONF.DIRECT_MODE)

    # STOP_ENABLE (bit 15)
    def set_stop_enable(self, enable):
        if enable:
            self.set_bit(GCONF.STOP_ENABLE)
        else:
            self.clear_bit(GCONF.STOP_ENABLE)

    def get_stop_enable(self):
        return self.get_bit(GCONF.STOP_ENABLE)

    # SMALL_HYSTERESIS (bit 14)
    def set_small_hysteresis(self, enable):
        if enable:
            self.set_bit(GCONF.SMALL_HYSTERESIS)
        else:
            self.clear_bit(GCONF.SMALL_HYSTERESIS)

    def get_small_hysteresis(self):
        return self.get_bit(GCONF.SMALL_HYSTERESIS)

    # DIAG1_PUSHPULL (bit 13)
    def set_diag1_pushpull(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG1_PUSHPULL)
        else:
            self.clear_bit(GCONF.DIAG1_PUSHPULL)

    def get_diag1_pushpull(self):
        return self.get_bit(GCONF.DIAG1_PUSHPULL)

    # DIAG0_PUSHPULL (bit 12)
    def set_diag0_pushpull(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG0_PUSHPULL)
        else:
            self.clear_bit(GCONF.DIAG0_PUSHPULL)

    def get_diag0_pushpull(self):
        return self.get_bit(GCONF.DIAG0_PUSHPULL)

    # DIAG1_ONSTATE (bit 10)
    def set_diag1_onstate(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG1_ONSTATE)
        else:
            self.clear_bit(GCONF.DIAG1_ONSTATE)

    def get_diag1_onstate(self):
        return self.get_bit(GCONF.DIAG1_ONSTATE)

    # DIAG1_INDEX (bit 9)
    def set_diag1_index(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG1_INDEX)
        else:
            self.clear_bit(GCONF.DIAG1_INDEX)

    def get_diag1_index(self):
        return self.get_bit(GCONF.DIAG1_INDEX)

    # DIAG1_STALL (bit 8)
    def set_diag1_stall(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG1_STALL)
        else:
            self.clear_bit(GCONF.DIAG1_STALL)

    def get_diag1_stall(self):
        return self.get_bit(GCONF.DIAG1_STALL)

    # DIAG0_STALL (bit 7)
    def set_diag0_stall(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG0_STALL)
        else:
            self.clear_bit(GCONF.DIAG0_STALL)

    def get_diag0_stall(self):
        return self.get_bit(GCONF.DIAG0_STALL)

    # DIAG0_OTPW (bit 6)
    def set_diag0_otpw(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG0_OTPW)
        else:
            self.clear_bit(GCONF.DIAG0_OTPW)

    def get_diag0_otpw(self):
        return self.get_bit(GCONF.DIAG0_OTPW)

    # DIAG0_ERROR (bit 5)
    def set_diag0_error(self, enable):
        if enable:
            self.set_bit(GCONF.DIAG0_ERROR)
        else:
            self.clear_bit(GCONF.DIAG0_ERROR)

    def get_diag0_error(self):
        return self.get_bit(GCONF.DIAG0_ERROR)

    # SHAFT (bit 4)
    def set_shaft(self, enable):
        if enable:
            self.set_bit(GCONF.SHAFT)
        else:
            self.clear_bit(GCONF.SHAFT)

    def get_shaft(self):
        return self.get_bit(GCONF.SHAFT)

    # MULTISTEP_FILT (bit 3)
    def set_multistep_filt(self, enable):
        if enable:
            self.set_bit(GCONF.MULTISTEP_FILT)
        else:
            self.clear_bit(GCONF.MULTISTEP_FILT)

    def get_multistep_filt(self):
        return self.get_bit(GCONF.MULTISTEP_FILT)

    # EN_PWM_MODE (bit 2)
    def set_en_pwm_mode(self, enable):
        if enable:
            self.set_bit(GCONF.EN_PWM_MODE)
        else:
            self.clear_bit(GCONF.EN_PWM_MODE)

    def get_en_pwm_mode(self):
        return self.get_bit(GCONF.EN_PWM_MODE)

    # FAST_STANDSTILL (bit 1)
    def set_fast_standstill(self, enable):
        if enable:
            self.set_bit(GCONF.FAST_STANDSTILL)
        else:
            self.clear_bit(GCONF.FAST_STANDSTILL)

    def get_fast_standstill(self):
        return self.get_bit(GCONF.FAST_STANDSTILL)


class IHOLD_IRUN:
    # Bit field positions
    IRUNDELAY = 24    # Bits 27:24
    IHOLDDELAY = 16   # Bits 19:16
    IRUN = 8          # Bits 12:8
    IHOLD = 0         # Bits 4:0

    def __init__(self, ihold_irun_value=0):
        """Initialize with a default IHOLD_IRUN value (0 if not specified)."""
        self.ihold_irun_value = ihold_irun_value

    def set_bits(self, bit_position, value, num_bits):
        """Set specific bits in the register value."""
        mask = (1 << num_bits) - 1
        self.ihold_irun_value &= ~(mask << bit_position)  # Clear the bits
        self.ihold_irun_value |= (value & mask) << bit_position  # Set the new value

    def get_bits(self, bit_position, num_bits):
        """Get specific bits from the register value."""
        mask = (1 << num_bits) - 1
        return (self.ihold_irun_value >> bit_position) & mask

    # IRUNDELAY (Motor power-up delay) - 4 bits (Bits 27:24)
    def set_irundelay(self, value):
        """Set the IRUNDELAY value (0-15)."""
        self.set_bits(IHOLD_IRUN.IRUNDELAY, value, 4)

    def get_irundelay(self):
        """Get the IRUNDELAY value (0-15)."""
        return self.get_bits(IHOLD_IRUN.IRUNDELAY, 4)

    # IHOLDDELAY (Motor power-down delay) - 4 bits (Bits 19:16)
    def set_iholddelay(self, value):
        """Set the IHOLDDELAY value (0-15)."""
        self.set_bits(IHOLD_IRUN.IHOLDDELAY, value, 4)

    def get_iholddelay(self):
        """Get the IHOLDDELAY value (0-15)."""
        return self.get_bits(IHOLD_IRUN.IHOLDDELAY, 4)

    # IRUN (Motor run current) - 5 bits (Bits 12:8)
    def set_irun(self, value):
        """Set the IRUN value (0-31)."""
        self.set_bits(IHOLD_IRUN.IRUN, value, 5)

    def get_irun(self):
        """Get the IRUN value (0-31)."""
        return self.get_bits(IHOLD_IRUN.IRUN, 5)

    # IHOLD (Standstill current) - 5 bits (Bits 4:0)
    def set_ihold(self, value):
        """Set the IHOLD value (0-31)."""
        self.set_bits(IHOLD_IRUN.IHOLD, value, 5)

    def get_ihold(self):
        """Get the IHOLD value (0-31)."""
        return self.get_bits(IHOLD_IRUN.IHOLD, 5)
    
    def to_dict(self):
        """Returns a dictionary representation of the IHOLD_IRUN register."""
        return {
            "irundelay": self.get_irundelay(),
            "iholddelay": self.get_iholddelay(),
            "irun": self.get_irun(),
            "ihold": self.get_ihold(),
        }

    def __repr__(self):
        return f"IHOLD_IRUN(ihold_irun_value=0x{self.ihold_irun_value:08X})"

class CHOPCONF:
    # Bitfield positions and lengths
    DISS2VS = 31
    DISS2G = 30
    DEDGE = 29
    INTPOL = 28
    MRES = 24  # MRES is 4 bits long
    TPFD = 20  # TPFD is 4 bits long
    VHIGHCHM = 19
    VHIGHFS = 18
    TBL = 15  # TBL is 2 bits long
    CHM = 14
    DISFDCC = 12
    HEND_OFFSET = 9  # HEND_OFFSET is 4 bits long
    HSTRT_TFD = 4  # HSTRT_TFD is 3 bits long
    TOFF = 0  # TOFF is 4 bits long

    def __init__(self, raw_value=0x00000000):
        """Initialize the class with the raw CHOPCONF register value."""
        self.raw_value = raw_value

    # DISS2VS (bit 31)
    def get_diss2vs(self):
        return (self.raw_value >> CHOPCONF.DISS2VS) & 0x1

    def set_diss2vs(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.DISS2VS)) | ((value & 0x1) << CHOPCONF.DISS2VS)

    # DISS2G (bit 30)
    def get_diss2g(self):
        return (self.raw_value >> CHOPCONF.DISS2G) & 0x1

    def set_diss2g(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.DISS2G)) | ((value & 0x1) << CHOPCONF.DISS2G)

    # DEDGE (bit 29)
    def get_dedge(self):
        return (self.raw_value >> CHOPCONF.DEDGE) & 0x1

    def set_dedge(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.DEDGE)) | ((value & 0x1) << CHOPCONF.DEDGE)

    # INTPOL (bit 28)
    def get_intpol(self):
        return (self.raw_value >> CHOPCONF.INTPOL) & 0x1

    def set_intpol(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.INTPOL)) | ((value & 0x1) << CHOPCONF.INTPOL)

    # MRES (bits 27-24, 4 bits)
    def get_mres(self):
        return (self.raw_value >> CHOPCONF.MRES) & 0xF

    def set_mres(self, value):
        self.raw_value = (self.raw_value & ~(0xF << CHOPCONF.MRES)) | ((value & 0xF) << CHOPCONF.MRES)

    # TPFD (bits 23-20, 4 bits)
    def get_tpfd(self):
        return (self.raw_value >> CHOPCONF.TPFD) & 0xF

    def set_tpfd(self, value):
        self.raw_value = (self.raw_value & ~(0xF << CHOPCONF.TPFD)) | ((value & 0xF) << CHOPCONF.TPFD)

    # VHIGHCHM (bit 19)
    def get_vhighchm(self):
        return (self.raw_value >> CHOPCONF.VHIGHCHM) & 0x1

    def set_vhighchm(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.VHIGHCHM)) | ((value & 0x1) << CHOPCONF.VHIGHCHM)

    # VHIGHFS (bit 18)
    def get_vhighfs(self):
        return (self.raw_value >> CHOPCONF.VHIGHFS) & 0x1

    def set_vhighfs(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.VHIGHFS)) | ((value & 0x1) << CHOPCONF.VHIGHFS)

    # TBL (bits 16-15, 2 bits)
    def get_tbl(self):
        return (self.raw_value >> CHOPCONF.TBL) & 0x3

    def set_tbl(self, value):
        self.raw_value = (self.raw_value & ~(0x3 << CHOPCONF.TBL)) | ((value & 0x3) << CHOPCONF.TBL)

    # CHM (bit 14)
    def get_chm(self):
        return (self.raw_value >> CHOPCONF.CHM) & 0x1

    def set_chm(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.CHM)) | ((value & 0x1) << CHOPCONF.CHM)

    # DISFDCC (bit 12)
    def get_disfdcc(self):
        return (self.raw_value >> CHOPCONF.DISFDCC) & 0x1

    def set_disfdcc(self, value):
        self.raw_value = (self.raw_value & ~(0x1 << CHOPCONF.DISFDCC)) | ((value & 0x1) << CHOPCONF.DISFDCC)

    # HEND_OFFSET (bits 11-8, 4 bits)
    def get_hend_offset(self):
        return (self.raw_value >> CHOPCONF.HEND_OFFSET) & 0xF

    def set_hend_offset(self, value):
        self.raw_value = (self.raw_value & ~(0xF << CHOPCONF.HEND_OFFSET)) | ((value & 0xF) << CHOPCONF.HEND_OFFSET)

    # HSTRT_TFD (bits 7-4, 3 bits)
    def get_hstrt_tfd(self):
        return (self.raw_value >> CHOPCONF.HSTRT_TFD) & 0x7

    def set_hstrt_tfd(self, value):
        self.raw_value = (self.raw_value & ~(0x7 << CHOPCONF.HSTRT_TFD)) | ((value & 0x7) << CHOPCONF.HSTRT_TFD)

    # TOFF (bits 3-0, 4 bits)
    def get_toff(self):
        return (self.raw_value >> CHOPCONF.TOFF) & 0xF

    def set_toff(self, value):
        self.raw_value = (self.raw_value & ~(0xF << CHOPCONF.TOFF)) | ((value & 0xF) << CHOPCONF.TOFF)

    def to_dict(self):
        """Returns a dictionary of all the fields and their current values."""
        return {
            "diss2vs": self.get_diss2vs(),
            "diss2g": self.get_diss2g(),
            "dedge": self.get_dedge(),
            "intpol": self.get_intpol(),
            "mres": self.get_mres(),
            "tpfd": self.get_tpfd(),
            "vhighchm": self.get_vhighchm(),
            "vhighfs": self.get_vhighfs(),
            "tbl": self.get_tbl(),
            "chm": self.get_chm(),
            "disfdcc": self.get_disfdcc(),
            "hend_offset": self.get_hend_offset(),
            "hstrt_tfd": self.get_hstrt_tfd(),
            "toff": self.get_toff(),
        }

    def __repr__(self):
        return f"CHOPCONF(raw_value=0x{self.raw_value:08X})"


