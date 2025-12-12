from i2c_wrapper import I2CWrapper


# PCA6408A register addresses (standard NXP mapping)
INPUT_PORT_REG = 0x00       # Read-only
OUTPUT_PORT_REG = 0x01      # R/W
POLARITY_INVERT_REG = 0x02  # R/W
CONFIG_REG = 0x03           # R/W, 1 = input, 0 = output


class PCA6408A:
    """
    Simple PCA6408A driver that uses an I2CWrapper instance.

    I2CWrapper is expected to be configured with the correct scl/sda pins
    and the target device address (e.g. 0x21 for the 5V ILEM expander).
    """

    REG_INPUT = INPUT_PORT_REG
    REG_OUTPUT = OUTPUT_PORT_REG
    REG_POLARITY = POLARITY_INVERT_REG
    REG_CONFIG = CONFIG_REG

    def __init__(self, i2c_wrapper: I2CWrapper):
        self.i2c_wrapper = i2c_wrapper
        self.i2c = i2c_wrapper.i2c
        self.addr = i2c_wrapper.i2c_address

    # --- low-level helpers -------------------------------------------------
    def _write_reg(self, reg, value):
        """Write a single register (0x00–0x03) with one byte of data."""
        self.i2c.writeto(self.addr, bytes([reg, value & 0xFF]))

    def _read_reg(self, reg):
        """Read a single register (0x00–0x03) and return its byte value."""
        self.i2c.writeto(self.addr, bytes([reg]))
        data = self.i2c.readfrom(self.addr, 1)
        return data[0]

    # --- configuration ------------------------------------------------------
    def set_config(self, mask_inputs):
        """
        Configure direction for all pins at once.

        mask_inputs: bit = 1 -> input, bit = 0 -> output (bit 0 = P0, bit 7 = P7)
        """
        self._write_reg(self.REG_CONFIG, mask_inputs)

    def get_config(self):
        return self._read_reg(self.REG_CONFIG)

    # --- outputs ------------------------------------------------------------
    def write_outputs(self, value):
        """Write all 8 output bits at once (bit 0 = P0, bit 7 = P7)."""
        self._write_reg(self.REG_OUTPUT, value)

    def read_outputs(self):
        """Read back the OUTPUT register (last written value)."""
        return self._read_reg(self.REG_OUTPUT)

    def pin_mode(self, pin, is_input):
        """Configure a single pin as input (True) or output (False)."""
        cfg = self._read_reg(self.REG_CONFIG)
        if is_input:
            cfg |= (1 << pin)
        else:
            cfg &= ~(1 << pin)
        self._write_reg(self.REG_CONFIG, cfg)

    def digital_write(self, pin, level):
        """Set one pin HIGH (True) or LOW (False)."""
        out = self._read_reg(self.REG_OUTPUT)
        if level:
            out |= (1 << pin)
        else:
            out &= ~(1 << pin)
        self._write_reg(self.REG_OUTPUT, out)

    # --- inputs -------------------------------------------------------------
    def read_inputs(self):
        """Return raw 8-bit INPUT register (bit 0 = P0, bit 7 = P7)."""
        return self._read_reg(self.REG_INPUT)

    def digital_read(self, pin):
        """Return 0/1 for the selected input pin."""
        return 1 if (self.read_inputs() & (1 << pin)) else 0

    # --- polarity -----------------------------------------------------------
    def set_polarity(self, mask_invert):
        """
        Configure input polarity inversion.

        mask_invert: bit = 1 -> invert that input pin, bit = 0 -> normal.
        """
        self._write_reg(self.REG_POLARITY, mask_invert)

    def get_polarity(self):
        return self._read_reg(self.REG_POLARITY)


