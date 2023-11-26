"""Shared libraries across CPython and MicroPython.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.

General guidelines:
    - Use other huereka/shared/* libraries when possible over "native" libraries.
    - If a "native" library is used, ensure there is an equivalent in MicroPython, or micropython-lib, that can be used.
    - Avoid branches based on CPython vs MicroPython, but if needed, use environments.is_micro_python() for detection.

Python module best practices:
    __future__:
        - Ensure it is supported by MicroPython, and add placeholder to uhuereka/src/lib/__future__.py.
    builtins
        FileNotFoundError:
            - Use OSError and check for errno == 2.
        str:
            - Use individual .startswith() checks instead of combined; iterables are not supported in MicroPython.
            - Use .replace() instead of .removeprefix() and .removesuffix().
    abc:
        - Avoid where possible. No abstraction checking is performed in MicroPython.
        - Do not use ABCMeta; metaclass is not supported in MicroPython. Use abc.ABC as a standard parent.
        - Basic support is available for ABC (class), abstractproperty (class), and abstractmethod (function).
    json:
        - Avoid advanced features, e.g., pretty-printing.
    logging:
        - Include "exc_info=exception" when calling Logger.exception to guarantee printing stacktraces in MicroPython.
    os:
        - Use pathlib where possible.
    shutil:
        - Avoid completely. Use os or pathlib instead.
    threading:
        - Do not require; make usage opt-in, instead of opt-out.
        - Currently experimental/unsafe in most MicroPython environments.
    types/typing:
        - Ensure an equivalent placeholder is available/added to uhuereka/src/lib/*.
"""
