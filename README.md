# Huereka!

[![os: linux](https://img.shields.io/badge/os-linux-blue)](https://docs.python.org/3.12/)
[![raspberry-pi](https://img.shields.io/badge/-Raspberry_Pi-C51A4A?logo=Raspberry-Pi&logoColor=white)](https://www.raspberrypi.com/)
[![arduino](https://img.shields.io/badge/-Arduino-00979D?logo=arduino&logoColor=white)](https://www.raspberrypi.com/)
[![python: 3.12+](https://img.shields.io/badge/python-3.12+-blue)](https://devguide.python.org/versions)
[![python: Micropython](https://img.shields.io/badge/python-MicroPython-blue)](https://micropython.org)
[![python style: google](https://img.shields.io/badge/python%20style-google-blue)](https://google.github.io/styleguide/pyguide.html)
[![imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://github.com/PyCQA/isort)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![code style: pycodestyle](https://img.shields.io/badge/code%20style-pycodestyle-green)](https://github.com/PyCQA/pycodestyle)
[![doc style: pydocstyle](https://img.shields.io/badge/doc%20style-pydocstyle-green)](https://github.com/PyCQA/pydocstyle)
[![static typing: mypy](https://img.shields.io/badge/static_typing-mypy-green)](https://github.com/python/mypy)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/PyCQA/pylint)
[![testing: pytest](https://img.shields.io/badge/testing-pytest-yellowgreen)](https://github.com/pytest-dev/pytest)
[![security: bandit](https://img.shields.io/badge/security-bandit-black)](https://github.com/PyCQA/bandit)
[![license: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-lightgrey)](LICENSE)


### Smart home automation platform.

Huereka! is a home-grown automation platform for hobbyists. Originally a way to control home decorative lighting,
such as RGB holiday lights, it also allows control of other basic electronic devices via various microcontrollers.

> **Note**: This is a hobbyist home automation and lighting platform, and does provide any guarantees around
new features being added, or bugs being fixed. Feel free to fork and share as you wish. Bugs and features are
addressed on a best effort basis.


### Table Of Contents

  * [Requirements](#requirements)
  * [Recommendations](#recommendations)
  * [API Quick Start](#api-quick-start)
  * [Additional Guides](#additional-guides)
  * [Design Overview](#design-overview)


### Requirements

* Read [Neopixel Uberguide](https://learn.adafruit.com/adafruit-neopixel-uberguide) to understand best practices.
* Huereka
  * Python3.12+
  * Controller with GPIO pins
  * LED lights with WS2811 microcontrollers
  * If controlling 12V lights:
    * Microcontroller with 5V GPIO pins, such as Arduino (Raspberry Pi only provides 3V)
    * Alternatively, a 3V to 5V level shifter may be used for the data signal
  * Possibly required for 5V lights depending on light model and using a controller with 5V GPIO pins
    * A 5V to 3V level shifter for data signal
* uHuereka
  * MicroPython compatible microcontroller.
  * Refer to [uHuereka Requirements](uhuereka/README.md#requirements) for more details.


### Recommendations

* Raspberry Pi 3+ or equivalent hardware for Huereka, or ESP32/RP2040+ for uHuereka.
* Refer to [uHuereka Recommendations](uhuereka/README.md#recommendations) for more details.


### API Quick Start

#### Huereka

1. Read the NeoPixel Uberguide to understand the best practices:
[Adafruit Neopixel Uberguide](https://learn.adafruit.com/adafruit-neopixel-uberguide)

2. Set up hardware and software environments with: [How to Set up Raspberry Pi](SETUP.md)

3. Start server with:
    ```
    huereka/server.py
    ```

4. Attempt to check the status from an external client:
    ```
    curl -k http://127.0.0.1:443/health
    ```

5. Create a new color profile:
    ```
    curl -k -X POST http://127.0.0.1:443/api/v1/profiles -d '{"name": "redtest", "colors": ["#FF0000"]}'
    ```

6. Create a new color schedule:
    ```
    curl -k http://127.0.0.1:443/api/v1/schedules -d '{"name": "redtest", "routines": [{"profile": "redtest", "days": 127}]}'
    ```

7. The lights should all turn red if the setup is complete. If no lights turn on, ensure the full setup has been
   performed and attempt the basic LED/GPIO tests.


#### uHuereka

1. Follow one of the [MicroPython Setups](uhuereka/README.md#micropython-setups) for your microcontroller.

2. Find the new device address on the network via MicroPython console, router configuration, or `arp -a`.

3. Attempt to check the status from an external client:
    ```
    curl -k http://<address>:443/health
    ```

3. Request the available managers:
    ```
    curl -k http://<address>:443/api/v1/managers
    ```

4. Turn one of the managers on:
    ```
    curl -k -X POST http://<address>:443/api/v1/managers/<uuid of manager> -d '{"mode":1}'
    ```

5. The connected LED to the pin should turn on if the setup is complete. If LED does not turn on,
ensure the full setup has been performed and try again, or check the logs via MicroPython console.

6. Turn off the manager:
    ```
    curl -k -X POST http://<address>:443/api/v1/managers/<uuid of manager> -d '{"mode":0}'
    ```


### Additional Guides

[Set up Huereka LED Test Hardware](SETUP.md#set-up-huereka-testing-hardware)  
[Set up Huereka Service to Start on Boot](SETUP.md#set-up-huereka-service-to-start-on-boot)  
[Improve Raspberry Pi Boot Time](SETUP.md#improve-raspberry-pi-boot-time)  
[uHuereka (Micro-Huereka) Set Up](uhuereka/README.md)  
[Other Set Up Guides](SETUP.md)


### Design Overview

Huereka has a few components used to control the automation hardware. The following is a high level overview of each
core component, but each component may also contain smaller components not listed here. The overall flow can be
summarized as: schedules wrap around routines, and routines wrap around profiles, and profiles wrap around devices.

**ColorProfile**: Saved collection of colors which can be used by lighting routines to make patterns
- Colors: RGB colors to use when creating patterns
- Mode: Flag used to control how colors are converted into patterns. e.g. mirror, repeat, etc.

**LEDManager**: Primary controller for enabling, disabling, and updating active LEDs
- LED count: Total number of LEDs controlled by the pin
- Pin: GPIO pin on the system to send control signals
- Active colors/LEDs: Current colors set on each LED

**LightingRoutine**: Conditions used to trigger color profiles
- Profile: Which color profile to use when conditions are met
- Days: Which days of the week the routine can be turned on
- Start: First moment of each day the routine would turn on
- End: Last moment of each day the routine will be on before turning off

**LightingSchedule**: Collection of lighting routines and the LED managers
- Manager: Which LED manager to send lighting routine updates to
- Routines: Collection of lighting routines which can trigger LED updates

**uHuereka**: Miniature version of Huereka designed for MicroPython
- Pronounced Micro-Huereka
- Designed to run on microcontrollers with low memory, CPU, etc.
- Contains minimal features compared to the full size library.
