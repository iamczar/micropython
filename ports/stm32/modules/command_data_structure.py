import struct

## later you need to have a MSG_ID as the header do you know how to pack and unpack incoming commands 

import struct

class ValveAndAirPumpCmds:
    
    valve1=1
    valve2=2 
    valve3=3  
    valve4=4
    valve5=5
    valve6=6  
    valve7=7  
    valve8=8 
    valve9=9
    valve10=10  
    airpump1=11
    airpump2=12
    
    def __init__(self):
        # Use a 16-bit integer to store the states of valves (1-10) and air pumps (1-2)
        self.states = 0b0000000000000000  # 16 bits, all initially set to 0

    def set_valve_air_pump(self, valve_index, state):
        if state:
            self.states |= (1 << (valve_index - 1))  # Set bit
        else:
            self.states &= ~(1 << (valve_index - 1))  # Clear bit

    def pack(self):
        # Pack the 16-bit integer as a single unsigned short (H format)
        fmt = "H"  # 16-bit unsigned integer
        return struct.pack(fmt, self.states)

    def unpack(self, data):
        # Unpack the 16-bit integer and update the states
        fmt = "H"
        (self.states,) = struct.unpack(fmt, data)

    def get_valve_airpump_state(self, valve_index):
        return bool(self.states & (1 << (valve_index - 1)))


class OxyPumpCmds:
       
    def __init__(self):
        self.circFlowSpeed: int = 1
        self.oxySP: float = 1.0
        self.oxyKp: float = 1.0
        self.oxyKi: float = 1.0
        self.oxyKd: float = 1.0
        self.pump1dir: int = 1
        self.tube_bore:int = 1
        self.pump_2_speed_ratio: float = 1.0
        
    def pack(self):
        fmt = "iffffBBf"  # int, 4 floats, bool, int, float
        return struct.pack(fmt, self.circFlowSpeed, self.oxySP, self.oxyKp, self.oxyKi, self.oxyKd,
                           self.pump1dir, self.tube_bore, self.pump_2_speed_ratio)

    def unpack(self, data):
        try:
            fmt = "iffffBBf"
            unpacked_data = struct.unpack(fmt, data)
            (self.circFlowSpeed, self.oxySP, self.oxyKp, self.oxyKi, self.oxyKd,
            self.pump1dir, self.tube_bore, self.pump_2_speed_ratio) = unpacked_data
        except Exception as e:
            print(f"Unable to pack Oxypump")

class PressurePumpCmds:
       
    def __init__(self):
        self.pressureFlowSpeed: int = 1
        self.pressureSP: float = 1.0
        self.pressureKp: float = 1.0
        self.pressureKi: float = 1.0
        self.pressureKd: float = 1.0
        self.pump2dir:int = 1
        self.tube_bore:int = 1

    def pack(self):
        fmt = "iffffBB"  # int, 4 floats, int
        return struct.pack(fmt, 
                           self.pressureFlowSpeed, 
                           self.pressureSP, 
                           self.pressureKp, 
                           self.pressureKi,
                           self.pressureKd,
                           self.pump2dir, 
                           self.tube_bore)

    def unpack(self, data):
        fmt = "iffffBB"
        unpacked_data = struct.unpack(fmt, data)
        (self.pressureFlowSpeed, 
         self.pressureSP, 
         self.pressureKp, 
         self.pressureKi, 
         self.pressureKd,
         self.pump2dir,
         self.tube_bore) = unpacked_data
    
class AutoSamplerCmds:
    def __init__(self):
        self.id: int = 0
        self.cmd: int = 0
        self.hold_time_hrs: int = 0
        
    def pack(self):
        fmt = "3i"  # 3 integers
        return struct.pack(fmt, self.id, self.cmd, self.hold_time_hrs)

    def unpack(self, data):
        fmt = "3i"
        unpacked_data = struct.unpack(fmt, data)
        (self.id, self.cmd, self.hold_time_hrs) = unpacked_data