# uHuereka

uHuereka (pronounced Micro-Huereka) is a miniaturized version of Huereka designed for MicroPython. It is designed
to run on microcontrollers with low memory, CPU, etc., and only contains minimal features compared to the
full size library.

### READ THIS NOTICE BEFORE CONTINUING

> **CAUTION: Improper grounding, voltage, and other interactions with electricity, can cause personal injury or
damage to your surroundings. By using this guide you agree to take proper precautions and assume full responsibility.**


### Table Of Contents

* [Requirements](#requirements)
* [Recommendations](#recommendations)
* [MicroPython Setups](#micropython-setups)
  * [Download MicroPython](#download-micropython)
  * [Set Up MicroPython on RP2040 devices](#set-up-micropython-on-rp2040-devices)
  * [Set Up MicroPython on ESP devices](#set-up-micropython-on-esp-devices)
* [uHuereka Setups](#uhuereka-setups)
  * [Set Up uHuereka on Host](#set-up-uhuereka-on-host)
  * [Set Up uHuereka on Microcontroller](#set-up-uhuereka-on-microcontroller)
* [Accessing MicroPython Environments](#accessing-micropython-environments)
  * [Access MicroPython Environment on Microcontroller via GUI](#access-micropython-environment-on-microcontroller-via-gui)
  * [Access MicroPython Environment on Microcontroller via CLI](#access-micropython-environment-on-microcontroller-via-cli)
* [Advanced Setups](#advanced-setups)
  * [Set Up Micropython Development Environment](#set-up-micropython-development-environment)
* [FAQ](#faq)


### Requirements

* Microcontroller capable of running MicroPython
* Wi-Fi capable microcontroller, or Wi-Fi adapter compatible with MicroPython, if using Wi-Fi features
* Bluetooth capable microcontroller, or Bluetooth adapter compatible with MicroPython, if using bluetooth features


### Recommendations

* RP2040 device
  * Raspberry Pi Pico W (Wireless)
  * Raspberry Pi Pico (No Wireless)
  * Seeed Studio XIAO RP2040 (No Wireless)
* ESP32 device
  * Seeed Studio XIAO ESP32-C3 (Wireless)


## MicroPython Setups

### Download MicroPython

Find and download a bootloader from official MicroPython repositories for your hardware:  
https://micropython.org/download/

### Set Up MicroPython on RP2040 devices

1. Hold down BOOTSEL button and plug in to computer. Release button after plugged in.

2. Open the RP2040 device like a disk drive, and copy the .uf2 firmware directly to it. Will auto reboot after upload.

### Set Up MicroPython on ESP devices

Installation may very from device to device. General guidelines below are based off ESP32 like device.
For full information on how to use 'esptool', refer to:  
https://github.com/espressif/esptool

1. Ensure local development is set up and active per [Set Up Huereka Development Environment](../SETUP.md#set-up-huereka-development-environment)

2. Install `esptool`.
   ```bash
   pip install esptool
   ```

3. Hold down BOOT button and plug in to computer. Release button after plugged in.

4. Verify the device is found:
   ```bash
   esptool.py flash_id
   ```

5. If the device is found and correct, collect the serial port value and continue. If not, troubleshoot device.

6. Follow the instructions for installation for your device from:
    https://micropython.org/download/


## uHuereka Setups

### Set Up uHuereka on Host

1. Ensure local development is set up and active per [Set Up Huereka Development Environment](../SETUP.md#set-up-huereka-development-environment)

2. Install `mpremote` for managing files and dependencies on the microcontrollers.
   ```bash
   pip install mpremote
   ```

### Set Up uHuereka on Microcontroller

1. Ensure microcontroller access via CLI is ready per [Set Up uHuereka on Host](#set-up-uhuereka-on-host)

2. Optional: Add a Wi-Fi config before install/sync to automatically connect on boot.
   If no config is added, it will automatically start a temporary Wi-Fi network for direct connection and configuration.
   To pre-configure, add a `wifi.json` under `src/`:
   ```bash
   [
     {
       "ssid": "<network name>",
       "bssid": <hardware address to force connection to specific AP, or null>,
       "password": "<password>",
       "hostname": "<name of the host on the network>",
     }
   ]
   ```

3. Optional: Add a manager config to automatically configure device on boot.
   If no config is added, managers will have to be configured manually through the API or a text editor.
   To pre-configure, add a `power_managers.json` under `src/`. Examples can be found or copied from `examples/`.
   ```bash
   # Example to set up an ESP32-C3 device with 2 power toggle managers on pins 2 and 3:
   cp uhuereka/examples/power_managers_esp32-c3.json uhuereka/src/power_managers.json
   ```

4. Run installer to copy over uHuereka source and install required MicroPython dependencies.
   ```bash
   uhuereka/install.sh --device <USB port microcontroller is connected to> --src --deps
   # Example:
   uhuereka/install.sh --device /dev/ttyUSB0 --src --deps
   ```


## Accessing MicroPython Environments

### Access MicroPython Environment on Microcontroller via GUI

Thonny provides an interactive IDE with REPL CLI built in. It can also be used to manage the files saved to the devices.
For more information on installing and using Thonny, visit:  
https://github.com/thonny/thonny

### Access MicroPython Environment on Microcontroller via CLI

1. Ensure microcontroller access via CLI is ready per [Set Up uHuereka on Host](#set-up-uhuereka-on-host)

2. Open mpremote REPL:
   ```bash
   mpremote
   # With device pre-specified
   mpremote connect <USB port microcontroller is connected to>
   # Example:
   mpremote connect /dev/ttyUSB0
   ```

3. Verify microcontroller library access and model:
   ```python
   import os;os.uname()
   ```

4. If available, you can now manage files on the device from `/pyboard`, or run other commands available in `help`.


## Advanced Setups

### Set Up Micropython Development Environment

While a large portion of standard Python code will run in MicroPython, it is not a 1-to-1 match, nor is it
intended to be to optimize resource usage. You can set up a MicroPython development environment without
a microcontroller for testing and contributing back to MicroPython. Here is an example of how to set up a
MicroPython environment from source inside a Docker. The steps may be applicable outside Docker depending on
your environment, but your mileage may vary.

1. Recommended to use `debian:bullseye` docker to isolate installation.
   ```bash
   # To mount a local development folder:
   docker run --rm -it -v <local path>:<target path> debian:bullseye bash

   # Example:
   docker run --rm -it -v ~/Development/huereka:/mnt/huereka debian:bullseye bash

   # Basic run with no access externally:
   docker run --rm -it debian:bullseye bash
   ```

2. Set up the OS:
   ```bash
   apt-get update && apt-get install -y build-essential curl libffi-dev git pkg-config python-dev python3 python3-venv python3-pip vim wget
   ```

3. Set up and build MicroPython:
   ```bash
   git clone https://github.com/micropython/micropython
   cd micropython/
   make -C mpy-cross
   cd ports/unix
   make submodules
   make
   ```

4. Test binary:
   ```bash
   build-standard/micropython -c "import sys; print(sys.implementation)"
   ```

5. Copy final executable to a local path for quick access if it was successful:
   ```bash
   cp build-standard/micropython /usr/bin/micropython
   ```


## FAQ

- Q: I am hitting "Wifi Unknown Error 0x0101" during boot, what is the cause, and how do I prevent?  
    - A: The microcontroller is most likely running out of memory during imports and initialization.
    Ensure you are using `.mpy` compiled files as much as possible for imports.