from machine import UART, Pin
from pyb import UART
from simple_logger import SimpleLogger
import pyb
import utime

class UARTWrapperTMC:
    def __init__(self, uart_bus, baudrate, timeout=1000, timeout_char=1000,logger:SimpleLogger=None):
        self.logger = logger
        try:
            self.uart_bus = uart_bus
            self.baudrate = baudrate
            self.uart = UART(self.uart_bus,self.baudrate)
            self.timeout = timeout
            self.timeout_char = timeout_char
            self.uart.init(self.baudrate, bits=8, parity=None, stop=1, timeout=self.timeout, timeout_char=self.timeout_char)
            self.logger.debug(f"UARTWrapperTMC setup complete")
        except Exception as e:
            self.logger.debug(f"Failed to set up UARTWrapperTMC")
                   
    def re_init_uart(self):
        self.uart.init(self.baudrate, bits=8, parity=None, stop=1, timeout=self.timeout, timeout_char=self.timeout_char)
        
    def send(self, data):
        self.re_init_uart()
        self.clear_buffer()
        self.logger.debug(f"sending data: {data}")
        self.uart.write(bytes(data))
        single_wire_pin = Pin(pyb.Pin.cpu.C6, Pin.IN)  # Initially set to output for sending
   
    def send_recv(self,data):
        self.re_init_uart()
        self.clear_buffer()
        self.logger.debug(f"sending data: {data}")
        self.uart.write(bytes(data))
        single_wire_pin = Pin(pyb.Pin.cpu.C6, Pin.IN)  # Initially set to output for sending

        utime.sleep(0.5)   # Give some time for the TMC2240 to respond

        if self.uart.any():
            # Data is available, read it
            data = self.uart.read()

            # Remove the first 4 bytes (read_access_datagram)
            data = data[4:]
            self.logger.debug(f"Recieved data: {data}")
            return data
        else:
            self.logger.debug(f"No data received")
            return None
            
    def clear_buffer(self):
        """Clear any remaining data in the UART buffer."""
        while self.uart.any():
            self.uart.read()

    def close(self):
        """
        Closes the UART connection.
        """
        self.logger.info("Closing UART connection in UARTWrapperTMC.")
        self.uart.deinit()  # Deinitialize the UART 
