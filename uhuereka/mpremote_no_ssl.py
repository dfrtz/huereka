#! /usr/bin/env python3

"""SSL verification disabled version of mpremote.

Prefer using standard "mpremote" where possible. This command is only available to help ignore SSL failures
on systems where either updating trusted cert chains is not allowed, or not working as expected.

Example of errors seen, even though the cert chain for micropython/github should work:
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
"""

import ssl
import sys

from mpremote import main

ssl._create_default_https_context = ssl._create_unverified_context
sys.exit(main.main())
