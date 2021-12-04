
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


### Recommendations

* Raspberry Pi 3 or equivalent hardware


### API Quick Start

1. Setup hardware and software environments with: [How to setup Raspberry Pi](SETUP.md)

2. Start server with:
    ```
    huereka/server.py -a 0.0.0.0 -k <path to HTTPS key> -c <path to HTTPS cert>
    ```

4. Attempt to check the status from an external client:
    ```
    curl -k https://<hostname or ip>:<port>/health
    ```
