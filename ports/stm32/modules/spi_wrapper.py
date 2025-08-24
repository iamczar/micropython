import pyb
from pyb import SPI, Pin, delay


class SPIWrapper:
    def __init__(self, spi_bus=2, cs_pin=pyb.Pin.cpu.A5, baudrate=1000000, polarity=1, phase=1, firstbit=SPI.MSB, delay_time=5):
        self.cs = Pin(cs_pin, Pin.OUT_PP)
        self.spi = SPI(spi_bus, SPI.CONTROLLER, baudrate=baudrate, polarity=polarity, phase=phase, firstbit=firstbit)
        self.cs.high()  # Deselect the device
        self.delay_time = delay_time

    def send(self, data):
        try:
            # Ensure data is bytes or bytearray
            if isinstance(data, int):  # If data is a single byte as an int
                data = bytes([data])
            elif not isinstance(data, (bytes, bytearray)):
                raise ValueError("Data must be bytes, bytearray, or a single int representing a byte.")

            # #print("Select the device")
            # self.cs.low()  # Select the device
            # #print(f"sending this data: {data.hex()}")
            self.spi.send(data)
        except Exception as e:
            print(f"SPI send error: {e}")
        # finally:
        #     # print("Deselect the device")
        #     self.cs.high()  # Deselect the device

    def recv(self, length):
        try:
            # self.cs.low()  # Select the device
            data = self.spi.recv(length)
            return data
        except Exception as e:
            print(f"SPI receive error: {e}")
            return None
        # finally:
        #     self.cs.high()  # Deselect the device

    def send_recv(self, data,length):
        try:
            # Ensure data is bytes or bytearray
            if isinstance(data, int):  # If data is a single byte as an int
                data = bytes([data])
            elif not isinstance(data, (bytes, bytearray)):
                raise ValueError("Data must be bytes, bytearray, or a single int representing a byte.")

            self.cs.low()  # Select the device
            self.spi.send(data)
            response = self.spi.recv(length)
            return response
        except Exception as e:
            print(f"SPI send/recv error: {e}")
            return None
        finally:
            self.cs.high()  # Deselect the device
            
    def select_device(self):
        self.cs.low()
        
    def deselect_device(self):
        self.cs.high()
