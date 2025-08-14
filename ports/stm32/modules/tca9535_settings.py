class Register:
    CONFIG_REGISTER_0 = 0x06
    CONFIG_REGISTER_1 = 0x07
    OUTPUT_PORT_0 = 0x02 
    OUTPUT_PORT_1 = 0x03
    
class Port:
    INPUT_PORT_0 = 0x00
    INPUT_PORT_1 = 0x01
    OUTPUT_PORT_0 = 0x02 
    OUTPUT_PORT_1 = 0x03
    
class ConfigPort:
    OUTPUT_PORT_0 = 0x06 
    OUTPUT_PORT_1 = 0x07

class PinSettings:
    class State:
        high = 1
        low = 0
        
    class Pins:
        P00 = 0
        P01 = 1
        P02 = 2
        P03 = 3
        P04 = 4
        P05 = 5
        P06 = 6
        P07 = 7
        
        P10 = 0
        P11 = 1
        P12 = 2
        P13 = 3
        P14 = 4
        P15 = 5
        P16 = 6
        P17 = 7
        
    class Direction:
        OUTPUT = 0
        INPUT = 1
    
    @staticmethod
    def generate_port0_value(p00: Direction = Direction.INPUT, 
                             p01: Direction = Direction.INPUT, 
                             p02: Direction = Direction.INPUT, 
                             p03: Direction = Direction.INPUT, 
                             p04: Direction = Direction.INPUT, 
                             p05: Direction = Direction.INPUT, 
                             p06: Direction = Direction.INPUT, 
                             p07: Direction = Direction.INPUT):
        # Set or clear bits based on the arguments
        port0_value = (
            (p00 << 0) |
            (p01 << 1) |
            (p02 << 2) |
            (p03 << 3) |
            (p04 << 4) |
            (p05 << 5) |
            (p06 << 6) |
            (p07 << 7)
        )
        return port0_value
    
    @staticmethod
    def generate_port1_value(p10: Direction = Direction.INPUT, 
                             p11: Direction = Direction.INPUT, 
                             p12: Direction = Direction.INPUT, 
                             p13: Direction = Direction.INPUT, 
                             p14: Direction = Direction.INPUT, 
                             p15: Direction = Direction.INPUT, 
                             p16: Direction = Direction.INPUT, 
                             p17: Direction = Direction.INPUT):
        # Set or clear bits based on the arguments
        port1_value = (
            (p10 << 0) |
            (p11 << 1) |
            (p12 << 2) |
            (p13 << 3) |
            (p14 << 4) |
            (p15 << 5) |
            (p16 << 6) |
            (p17 << 7)
        )
        return port1_value