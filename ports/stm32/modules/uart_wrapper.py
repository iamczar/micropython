import select
from pyb import UART
import utime

class UARTWrapper:
    def __init__(self, uart_bus:int=0, baudrate:int=115200, uart_id:str=None):
        self.uart_bus = uart_bus
        self.baudrate = baudrate
        self.uart_id = uart_id
        try:
            self.uart = UART(self.uart_bus, self.baudrate)
            self.uart.init(self.baudrate, bits=8, parity=None, stop=1, timeout=1000, timeout_char=100)

            # Initialize poll object and register the UART for input events
            self.poll = select.poll()
            self.poll.register(self.uart, select.POLLIN)  # POLLIN to indicate data is ready for reading
        except Exception as e:
            print(f"Error initializing UART: {self.uart_id} : {e}")

    def send(self, data):
        try:
            self.uart.write(data)
            utime.sleep_ms(10)  # Small delay to ensure the UART is ready for subsequent operations
        except Exception as e:
            print(f"Error sending data: {self.uart_id} {e}")

    def recv(self, nbytes, timeout=1000):
        """
        Uses select.poll() to wait for data to be available with a timeout.
        :param nbytes: Number of bytes to read.
        :param timeout: Maximum time (in milliseconds) to wait for data.
        :return: Received data or empty bytes if timeout occurs.
        """
        try:
            events = self.poll.poll(timeout)
            if events:
                # Data is available, read from the UART
                response = self.uart.read(nbytes)
                if response is None:
                    return b''  # No data received
                return response
            return b''  # Timeout occurred, no data received
        except Exception as e:
            print(f"Error receiving data: {self.uart_id} : {e}")
            return b''

    def clear_buffer(self):
        try:
            while self.uart.any():
                self.uart.read()
        except Exception as e:
            print(f"Error clearing buffer: {self.uart_id} : {e}")
