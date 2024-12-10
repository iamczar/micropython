include("$(PORT_DIR)/boards/manifest.py")
include("$(PORT_DIR)/boards/manifest_pyboard.py")

freeze("$(PORT_DIR)/modules", "uart_wrapper_tmc.py")
freeze("$(PORT_DIR)/modules", "tmc2240_settings.py")
freeze("$(PORT_DIR)/modules", "tmc2240.py")
freeze("$(PORT_DIR)/modules", "stepper_motor_uart.py")

freeze("$(PORT_DIR)/modules", "i2c_wrapper.py")
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


