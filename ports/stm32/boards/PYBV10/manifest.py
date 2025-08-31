include("$(PORT_DIR)/boards/manifest.py")
include("$(PORT_DIR)/boards/manifest_pyboard.py")

freeze("$(PORT_DIR)/modules", "uart_wrapper_tmc.py")
freeze("$(PORT_DIR)/modules", "tmc2240_settings.py")
freeze("$(PORT_DIR)/modules", "tmc2240.py")
freeze("$(PORT_DIR)/modules", "stepper_motor_uart.py")

freeze("$(PORT_DIR)/modules", "i2c_wrapper.py")
freeze("$(PORT_DIR)/modules", "spi_wrapper.py")
freeze("$(PORT_DIR)/modules", "slf3c_1300f.py")
freeze("$(PORT_DIR)/modules", "tempflow_sensor.py")

freeze("$(PORT_DIR)/modules", "uart_wrapper.py")
freeze("$(PORT_DIR)/modules", "pico_o2_settings.py")
freeze("$(PORT_DIR)/modules", "pico_o2.py")
freeze("$(PORT_DIR)/modules", "oxygen_sensor.py")

freeze("$(PORT_DIR)/modules", "data_logger.py")
freeze("$(PORT_DIR)/modules", "config.py")

freeze("$(PORT_DIR)/modules", "event_bus.py")
freeze("$(PORT_DIR)/modules", "simple_logger.py")

# AlphaCommsManager (frozen Python module)
freeze("$(PORT_DIR)/modules", "alphacommsmanager.py")

# Controllers and Actuators moved into firmware (flat)
freeze("$(PORT_DIR)/modules", "command_data_structure.py")
freeze("$(PORT_DIR)/modules", "pressure_controller.py")
freeze("$(PORT_DIR)/modules", "circ_flow_controller.py")
freeze("$(PORT_DIR)/modules", "valve.py")
freeze("$(PORT_DIR)/modules", "valve_and_air_pump_actuator.py")
freeze("$(PORT_DIR)/modules", "tca9535.py")
freeze("$(PORT_DIR)/modules", "tca9535_settings.py")
freeze("$(PORT_DIR)/modules", "pid.py")

# Controllers moved into firmware
freeze("$(PORT_DIR)/modules", "sequence_controller.py")

# Sensors moved into firmware
freeze("$(PORT_DIR)/modules", "file_storage_sensor.py")

# Auto Sampler module
freeze("$(PORT_DIR)/modules", "auto_sampler.py")

