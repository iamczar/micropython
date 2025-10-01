# CellAg MicroPython STM32 Build Guide

## Purpose and Scope

This guide covers building custom STM32 MicroPython firmware for the CellAg cycler (PYBV11 board) with frozen Python modules from `ports/stm32/modules`. The firmware is flashed using STM32CubeProgrammer on Windows.

## Repository Structure

- **`ports/stm32/modules/`**: CellAg Python modules (sensors, controllers, actuators, wrappers)
- **`ports/stm32/boards/PYBV10/manifest.py`**: Manifest file controlling which modules get frozen into firmware
- **Note**: PYBV11 board uses PYBV10's manifest when it doesn't have its own

## Prerequisites

### Linux/WSL
- WSL Ubuntu (or native Linux)
- `make`, Python 3.3+
- ARM toolchain: `arm-none-eabi-gcc`
  ```bash
  sudo apt-get install gcc-arm-none-eabi binutils-arm-none-eabi
  ```
- Git submodules initialized

### Windows
- STM32CubeProgrammer installed
- Download from: https://www.st.com/en/development-tools/stm32cubeprog.html

## Build Workflow (Step-by-Step)

### 1. Build mpy-cross compiler (one-time setup)
From the repository root:
```bash
make -C mpy-cross
```

### 2. Initialize submodules for STM32 port (one-time setup)
```bash
cd ports/stm32
make BOARD=PYBV11 submodules
```

### 3. Edit module freeze list
Open `ports/stm32/boards/PYBV10/manifest.py` and add/remove `freeze()` lines as needed:
```python
freeze("$(PORT_DIR)/modules", "your_module.py")
```

### 4. Clean previous build
```bash
make clean
```

### 5. Build firmware for PYBV11
```bash
make BOARD=PYBV11
```

### 6. Locate firmware
The firmware will be generated at:
- `build-PYBV11/firmware.hex` (use this for STM32CubeProgrammer)
- `build-PYBV11/firmware.dfu` (alternative for DFU flashing)
- `build-PYBV11/firmware.elf` (for debugging)

## Frozen Modules Reference

Current modules frozen via `boards/PYBV10/manifest.py`:

### Motor Control
- `tmc2240.py` - TMC2240 stepper motor driver
- `tmc2240_settings.py` - TMC2240 configuration
- `stepper_motor_uart.py` - Stepper motor UART interface
- `uart_wrapper_tmc.py` - UART wrapper for TMC

### Sensors
- `slf3c_1300f.py` - SLF3C-1300F flow sensor
- `tempflow_sensor.py` - Temperature/flow sensor
- `pico_o2.py` - PicoO2 oxygen sensor driver
- `oxygen_sensor.py` - Oxygen sensor interface
- `pico_o2_settings.py` - PicoO2 configuration
- `file_storage_sensor.py` - File-based sensor logging

### I/O Expansion
- `tca9535.py` - TCA9535 I2C I/O expander
- `tca9535_settings.py` - TCA9535 configuration

### Controllers
- `pressure_controller.py` - Pressure control logic
- `circ_flow_controller.py` - Circulation flow control
- `sequence_controller.py` - Sequence orchestration
- `pid.py` - PID controller implementation

### Actuators
- `valve.py` - Valve control
- `valve_and_air_pump_actuator.py` - Combined valve/pump control

### Communication & Infrastructure
- `alphacommsmanager.py` - Alpha communications manager
- `event_bus.py` - Event bus for inter-module communication
- `data_logger.py` - Data logging
- `simple_logger.py` - Simple logging utility
- `config.py` - Configuration management

### Hardware Wrappers
- `i2c_wrapper.py` - I2C bus wrapper
- `spi_wrapper.py` - SPI bus wrapper
- `uart_wrapper.py` - UART wrapper

### Auto Sampling
- `auto_sampler.py` - Automated sampling control

## Flashing Firmware (Windows via STM32CubeProgrammer)

### 1. Enter DFU Mode
- Short **BOOT0** pin to **3.3V** on the cycler board
- Plug in USB cable (board enters DFU/bootloader mode)

### 2. Flash with STM32CubeProgrammer
1. Open STM32CubeProgrammer
2. Select **USB** connection in the right panel
3. Click **Connect** (verify board is enumerated)
4. Click **Open file** tab
5. Browse to `build-PYBV11/firmware.hex`
6. Click **Download** to flash

### 3. Reset Board
- Disconnect USB
- Remove BOOT0 jumper (disconnect from 3.3V)
- Power cycle or reconnect USB

## Verifying on Device

### Connect via Serial
**WSL/Linux:**
```bash
screen /dev/ttyACM0 115200
# or
mpremote
```

**Windows:**
- Use Thonny IDE, PuTTY, or Tera Term
- Connect to the virtual COM port at 115200 baud

### Test Frozen Modules
At the MicroPython REPL:
```python
>>> import tmc2240
>>> import valve
>>> import pressure_controller
>>> import oxygen_sensor
>>> print("All modules loaded successfully!")
```

If imports succeed without `ImportError`, the modules are frozen correctly!

## Adding or Updating Modules

### 1. Add/Edit Python Module
Place or modify `.py` file in `ports/stm32/modules/`:
```bash
cd ports/stm32/modules/
nano my_new_module.py
```

### 2. Update Manifest
Edit `ports/stm32/boards/PYBV10/manifest.py` and add:
```python
freeze("$(PORT_DIR)/modules", "my_new_module.py")
```

### 3. Rebuild Firmware
```bash
cd ports/stm32
make clean
make BOARD=PYBV11
```

### 4. Flash New Firmware
Use STM32CubeProgrammer to flash the new `build-PYBV11/firmware.hex`

## Troubleshooting

### "No module named …" Error
- ✅ Check `boards/PYBV10/manifest.py` has the correct `freeze()` entry
- ✅ Verify filename matches exactly (case-sensitive)
- ✅ Confirm you ran `make clean` before rebuilding
- ✅ Check the module file exists in `ports/stm32/modules/`

### Build Fails with Submodule Errors
```bash
make BOARD=PYBV11 submodules
```

### STM32CubeProgrammer Doesn't See Board
- ✅ Verify BOOT0 is jumpered to 3.3V **before** plugging in USB
- ✅ Check USB cable supports data (not charge-only)
- ✅ Try different USB port
- ✅ Reinstall STM32 USB drivers from STM32CubeProgrammer installation

### Firmware Too Large
- Remove unused modules from `manifest.py`
- Consider using `.mpy` precompiled bytecode (advanced)
- Enable LTO: `make BOARD=PYBV11 LTO=1`

### Wrong Board Compiled
- Always use `BOARD=PYBV11` for the CellAg cycler hardware
- PYBV10 is a different board variant

### Permission Denied on /dev/ttyACM0 (Linux/WSL)
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

## Important Notes

- **PYBV11 inherits PYBV10 manifest**: When PYBV11 lacks its own `manifest.py`, it uses PYBV10's, so editing `PYBV10/manifest.py` affects PYBV11 builds.
- **Always `make clean`**: This is crucial before rebuilding to avoid stale frozen module cache.
- **Firmware location**: After a successful build, always use `build-PYBV11/firmware.hex` for flashing.
- **Official MicroPython firmware**: For reference or fallback, download stock firmware from [micropython.org/download/PYBV11](https://micropython.org/download/PYBV11/)

## Build Options

### Clean Build (Recommended)
```bash
make clean
make BOARD=PYBV11
```

### With Link-Time Optimization (smaller firmware)
```bash
make clean
make BOARD=PYBV11 LTO=1
```

### Debug Build
```bash
make clean
make BOARD=PYBV11 DEBUG=1
```

### Check Build Output Size
After building, check firmware size:
```bash
ls -lh build-PYBV11/firmware.*
```

## Additional Resources

- [MicroPython STM32 Port Documentation](https://docs.micropython.org/en/latest/pyboard/)
- [MicroPython Forums](https://github.com/micropython/micropython/discussions)
- [STM32 Port README](README.md)
- [CellAg Cycler Repository](../../cellag/)

## Quick Reference Commands

```bash
# One-time setup
make -C mpy-cross
cd ports/stm32 && make BOARD=PYBV11 submodules

# Edit manifest
nano boards/PYBV10/manifest.py

# Build
make clean
make BOARD=PYBV11

# Output
ls -lh build-PYBV11/firmware.hex
```

