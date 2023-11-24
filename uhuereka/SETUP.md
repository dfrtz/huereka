# uHuereka

uHuereka (pronounced Micro-Huereka) is a miniature version of Huereka designed for MicroPython. It is designed
to run on microcontrollers with low memory, CPU, etc., and only contains minimal features compared to the
full size library.


#### Table Of Contents

* [Requirements](#requirements)
* [Recommendations](#recommendations)
* [MicroPython Setup](#micropython-setup)
  * [Download MicroPython](#download-micropython)
  * [Set Up MicroPython on RP2040 devices](#set-up-micropython-on-rp2040-devices)
  * [Set Up MicroPython on ESP devices](#set-up-micropython-on-esp-devices)
  * [Access MicroPython Environment on Microcontroller via GUI](#access-micropython-environment-on-microcontroller-via-gui)
  * [Access MicroPython Environment on Microcontroller via CLI](#access-micropython-environment-on-microcontroller-via-cli)
  * [Set Up Micropython Development Environment](#set-up-micropython-development-environment)


### Requirements

* Microcontroller capable of running MicroPython
* Wi-Fi capable microcontroller, or Wi-Fi adapter compatible with MicroPython, if using Wi-Fi features
* Bluetooth capable microcontroller, or Bluetooth adapter compatible with MicroPython, if using bluetooth features


### Recommendations

* RP2040 device
  * Raspberry Pi Pico (No Wireless)
  * Raspberry Pi Pico W (Wireless)
  * Seeed Studio XIAO RP2040 (No Wireless)
* ESP32 device
  * Seeed Studio XIAO ESP32-C3 (Wireless)


## MicroPython Setup

### Download MicroPython

Find and download a bootloader from official MicroPython repositories for your hardware:  
https://micropython.org/download/


### Set Up MicroPython on RP2040 devices

1. Hold down BOOTSEL button and plug in to computer. Release button after plugged in.

2. Open the Rpi Pico like a disk drive, and copy .uf2 firmware into directory. Will auto reboot after upload.


### Set Up MicroPython on ESP devices

Installation may very from device to device. General guidelines below are based off ESP32-C3 device.
For full information on how to use 'esptool', refer to:  
https://github.com/espressif/esptool

1. Ensure local development is set up and active per [Set Up Micropython Development Environment](../SETUP.md#set-up-huereka-development-environment)

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


### Access MicroPython Environment on Microcontroller via GUI

Thonny provides an interactive IDE with REPL CLI built in. It can also be used to manage the files saved to the devices.
For more information on installing and using Thonny, visit:  
https://thonny.org/


### Access MicroPython Environment on Microcontroller via CLI

1. Ensure local development is set up and active per [Set Up Micropython Development Environment](../SETUP.md#set-up-huereka-development-environment)

2. Install `rshell`.
   ```bash
   pip install rshell
   ```

3. Open rshell prompt:
   ```bash
   rshell
   ```

4. Verify microcontroller is visible:
   ```bash
   boards
   ```

5. If available, you can now manage files on the device from `/pyboard`, or run other commands available in `help`.


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
