# uHuereka

uHuereka (pronounced Micro-Huereka) is a miniature version of Huereka designed for MicroPython. It is designed
to run on microcontrollers with low memory, CPU, etc., and only contains minimal features compared to the
full size library.


#### Table Of Contents

* [Requirements](#requirements)
* [Recommendations](#recommendations)
* [Download MicroPython](#download-micropython)
* [Set Up MicroPython on Raspberry Pi Pico](#set-up-micropython-on-raspberry-pi-pico)
* [Access MicroPython Environment on Microcontroller](#access-micropython-environment-on-microcontroller)
* [Set Up Micropython Development Environment](#set-up-micropython-development-environment)


### Requirements

* Microcontroller capable of running MicroPython
* Bluetooth capable microcontroller, or Bluetooth adapter compatible with MicroPython, if using bluetooth features


### Recommendations

* Raspberry Pi Pico, Raspberry Pi Pico W, or similar


### Download MicroPython

Find and download a bootloader from official MicroPython repositories for your hardware:  
https://micropython.org/download/


### Set Up MicroPython on Raspberry Pi Pico

1. Hold down BOOTSEL button and plug in to computer. Release button after plugged in.

2. Open the Rpi Pico like a disk drive, and copy .uf2 firmware into directory. Will auto reboot after upload.


### Access MicroPython Environment on Microcontroller

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
