# /commswrappers/i2c_wrapper.py
from machine import SoftI2C


class I2CWrapper:
    def __init__(self,scl_pin,sda_pin,i2c_address, freq=100000):
        # Initialize SoftI2C with specified pins and frequency
        self.i2c = SoftI2C(scl=scl_pin,sda=sda_pin,freq=100000)
        self.i2c_address = i2c_address

    def send(self, data):
        self.i2c.writeto(self.i2c_address, data)

    def recv(self, length):
        return self.i2c.readfrom(self.i2c_address, length)
