
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

* Raspberry Pi 3 or equivalent hardware


### API Quick Start

1. Read the NeoPixel Uberguide to understand the best practices:
[Adafruit Neopixel Uberguide](https://learn.adafruit.com/adafruit-neopixel-uberguide)

2. Setup hardware and software environments with: [How to Setup Raspberry Pi](SETUP.md)

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
