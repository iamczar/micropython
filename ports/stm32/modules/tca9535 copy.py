from actuators.tca9535_settings import Register, PinSettings,ConfigPort,Port

class TCA9535:

    def __init__(self, i2c_wrapper,logger=None):
        self.i2c = i2c_wrapper
        self.logger = logger
       
    def read_register(self, reg):
        try:
            self.logger.debug(f"Reading register {reg:#04x}")
            self.i2c.send(bytearray([reg]))
            value = self.i2c.recv(1)[0]
            self.logger.debug(f"Read value {value:#04x} from register {reg:#04x}")
            return value
        except Exception as e:
            self.logger.error(f"Failed to read register {reg:#04x}: {e}")
            raise  # Re-raise the exception after logging
    
    def write_register(self, reg, value):
        try:
            self.logger.debug(f"Writing value {value:#04x} to register {reg:#04x}")
            self.i2c.send(bytearray([reg, value]))
        except Exception as e:
            self.logger.error(f"Failed to write value {value:#04x} to register {reg:#04x}: {e}")
            raise  # Re-raise the exception after logging

    def configure_pin(self, pin: PinSettings.Pins, direction: PinSettings.Direction, config_port: ConfigPort):
        try:
            self.logger.debug(f"Configuring pin {pin} on port {config_port} as {'OUTPUT' if direction == PinSettings.Direction.OUTPUT else 'INPUT'}")
            # Step 1: Read the current configuration register value
            current_value = self.read_register(config_port)

            # Step 2: Modify the bit corresponding to the pin
            if direction == PinSettings.Direction.OUTPUT:
                new_value = current_value & ~(1 << pin)  # Set bit to 0 for OUTPUT
            else:
                new_value = current_value | (1 << pin)  # Set bit to 1 for INPUT

            # Step 3: Write the modified value back to the register
            self.write_register(config_port, new_value)
        except Exception as e:
            self.logger.error(f"Failed to configure pin {pin}: {e}")

    def configure_all_pins(self, port0_direction, port1_direction):
        try:
            # Ensure that port0_direction and port1_direction are 8-bit values
            port0_direction = port0_direction & 0xFF  # Mask to ensure it's an 8-bit value
            port1_direction = port1_direction & 0xFF  # Mask to ensure it's an 8-bit value

            self.logger.debug(f"Configuring all pins on port 0 with value {port0_direction:#04x}")
            self.write_register(Register.CONFIG_REGISTER_0, port0_direction)

            self.logger.debug(f"Configuring all pins on port 1 with value {port1_direction:#04x}")
            self.write_register(Register.CONFIG_REGISTER_1, port1_direction)
        except Exception as e:
            self.logger.error(f"Failed to configure all pins: {e}")
            
            
    def set_all_pins_to_low(self):
        try:
            # Set all pins to low by writing 0 to the output registers
            self.logger.debug("Setting all pins on OUTPUT_PORT_0 to low")
            self.write_register(Register.OUTPUT_PORT_0, 0)

            self.logger.debug("Setting all pins on OUTPUT_PORT_1 to low")
            self.write_register(Register.OUTPUT_PORT_1, 0)
            
        except Exception as e:
            self.logger.error(f"Failed to set all pins to low: {e}")
        
        
    def get_port_configuration(self):
        try:
            # Read configuration registers for both ports
            port0_config = self.read_register(Register.CONFIG_REGISTER_0)
            port1_config = self.read_register(Register.CONFIG_REGISTER_1)

            # Interpret the configuration for each pin
            port_config = {}

            # Port 0 (P00 - P07)
            for pin in range(8):
                pin_name = f"P{pin}"
                if port0_config & (1 << pin):
                    port_config[pin_name] = "input"
                else:
                    port_config[pin_name] = "output"

            # Port 1 (P10 - P17)
            for pin in range(8):
                pin_name = f"P1{pin}"
                if port1_config & (1 << pin):
                    port_config[pin_name] = "input"
                else:
                    port_config[pin_name] = "output"

            # Return the port configuration as a dictionary
            return port_config

        except Exception as e:
            self.logger.error(f"Failed to get port configuration: {e}")       
        
    def set_pin(self,pin:PinSettings.Pins,value:PinSettings.State,port:Port):
        try:
            # Read the current output register value
            current_value = self.read_register(port)

            # Modify the bit corresponding to the pin
            if value == PinSettings.State.high:
                new_value = current_value | (1 << pin)  # Set the bit to 1
            else:
                new_value = current_value & ~(1 << pin)  # Set the bit to 0

            # Write the modified value back to the register
            self.write_register(port, new_value)
            self.logger.debug(f"Set pin {pin} on port {port} to {'HIGH' if value == PinSettings.State.high else 'LOW'}")
        except Exception as e:
            self.logger.error(f"Failed to set pin {pin} on port {port}: {e}")
        
    def get_pin_state(self,pin:PinSettings.Pins,port:Port):
        try:
            # Read the input register based on the port
            current_value = self.read_register(port)

            # Check the bit corresponding to the pin
            if current_value & (1 << pin):
                pin_state = PinSettings.State.high
            else:
                pin_state = PinSettings.State.low

            return pin_state
        except Exception as e:
            self.logger.error(f"Failed to get state for pin {pin} on port {port}: {e}")
            raise
        
    def get_all_pin_states(self, port: Port):
        try:
            # Read the entire port register value
            port_value = self.read_register(port)

            # Create a dictionary to store the states of all pins
            pin_states = {}
            for pin in range(8):
                pin_name = f"P{pin}"
                if port_value & (1 << pin):
                    pin_states[pin_name] = "high"
                else:
                    pin_states[pin_name] = "low"

            # Create the JSON structure
            result = {
                "port": port,
                "pins": pin_states
            }
            return result
        except Exception as e:
            self.logger.error(f"Failed to get states for all pins on port {port}: {e}")
            raise