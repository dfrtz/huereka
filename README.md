# Huereka

[![python: python3.9](https://img.shields.io/badge/python-3.9-blue)](https://docs.python.org/3.9/)
[![python style: google](https://img.shields.io/badge/python%20style-google-blue)](https://google.github.io/styleguide/pyguide.html)
[![code quality: pylint](https://img.shields.io/badge/code%20quality-pylint-green)](https://github.com/PyCQA/pylint)
[![code style: pycodestyle](https://img.shields.io/badge/code%20style-pycodestyle-green)](https://github.com/PyCQA/pycodestyle)
[![doc style: pydocstyle](https://img.shields.io/badge/doc%20style-pydocstyle-green)](https://github.com/PyCQA/pydocstyle)
[![security: bandit](https://img.shields.io/badge/security-bandit-black)](https://github.com/PyCQA/bandit)
[![license: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-lightgrey)](https://www.apache.org/licenses/LICENSE-2.0)

Decorative lighting management software.


### Requirements

* Python3.9+
* Controller with GPIO pins
* LED lights with WS2811 microcontrollers
* Read [Neopixel Uberguide](https://learn.adafruit.com/adafruit-neopixel-uberguide) to understand best practices.


### Recommendations

* Raspberry Pi 3+ or equivalent hardware


### API Quick Start

1. Read the NeoPixel Uberguide to understand the best practices:
[Adafruit Neopixel Uberguide](https://learn.adafruit.com/adafruit-neopixel-uberguide)

2. Set up hardware and software environments with: [How to Set up Raspberry Pi](SETUP.md)

3. Start server with:
    ```
    huereka/server.py -a 0.0.0.0 -k <path to HTTPS key> -c <path to HTTPS cert>
    ```

4. Attempt to check the status from an external client:
    ```
    curl -k https://<hostname or ip>:<port>/health
    ```

5. Create a new color profile:
    ```
    curl -k -X POST https://<hostname or ip>:<port>/api/v1/profiles -d '{"name": "redtest", "colors": ["#FF0000"]}'
    ```

6. Create a new color schedule:
    ```
    curl -k https://<hostname or ip>:<port>/api/v1/schedules -d '{"name": "redtest", "routines": [{"profile": "redtest", "days": 127}]}'
    ```

7. The lights should all turn red if the setup is complete. If no lights turn on, ensure the full setup has been
   performed and attempt the basic LED/GPIO tests.


### Design Overview

Huereka has a few components used to control the lighting hardware. The following is a high level overview of each
core component, but each component may also contain smaller components not listed here. The overall flow can be
summarized as: schedules wrap around routines, and routines wrap around profiles, and profiles wrap around LEDs.

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
