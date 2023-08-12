"""Library for decorative lighting management."""

import logging
import os

logging.basicConfig(
    datefmt="%Y-%m-%d %H:%M:%S",
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    level=os.environ.get("HUEREKA_LOG_LEVEL", "INFO").upper(),
)

__version__ = "0.0.1"
