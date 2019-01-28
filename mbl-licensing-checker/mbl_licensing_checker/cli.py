# Based on: src/pydocstyle/cli.py
# In open-source project: https://github.com/PyCQA/pydocstyle
#
# Original file: Copyright (c) 2014-2017 Amir Rachum, <http://amir.rachum.com/>
# Modifications: Copyright (c) 2019 Arm Limited and Contributors. All rights
#                reserved.
#
# SPDX-License-Idgenvtifier: MIT
"""Command line interface for mbl-licensing-checker."""
import logging
import sys
from enum import Enum

from .utils import log
from .violations import Error
from .config import ConfigurationParser, IllegalConfiguration
from .checker import check


class ReturnCode(Enum):
    """Application return codes."""

    NO_VIOLATIONS_FOUND = 0
    VIOLATIONS_FOUND = 1
    INVALID_OPTIONS = 2


def run_mbl_licensing_checker():
    """Application main algorithm."""
    log.setLevel(logging.DEBUG)
    conf = ConfigurationParser()
    _setup_stream_handlers(conf.get_default_run_configuration())

    try:
        conf.parse()
    except IllegalConfiguration:
        return ReturnCode.INVALID_OPTIONS.value

    run_conf = conf.get_user_run_configuration()

    # Reset the logger according to the command line arguments
    _setup_stream_handlers(run_conf)

    log.debug("starting in debug mode.")

    Error.explain = run_conf.explain

    errors = []

    try:
        for filename, checked_codes in conf.get_files_to_check():
            errors.extend(check((filename,), select=checked_codes))
    except IllegalConfiguration as error:
        log.error(error.args[0])
        return ReturnCode.INVALID_OPTIONS.value

    count = 0
    for error in errors:  # type: ignore
        if hasattr(error, "code"):
            sys.stdout.write("{}\n".format(error))
        count += 1
    if count == 0:
        exit_code = ReturnCode.NO_VIOLATIONS_FOUND.value
    else:
        exit_code = ReturnCode.VIOLATIONS_FOUND.value
    if run_conf.count:
        print(count)
    return exit_code


def main():
    """Run mbl-licensing-checker."""
    try:
        sys.exit(run_mbl_licensing_checker())
    except KeyboardInterrupt:
        print("Exiting the application")


def _setup_stream_handlers(conf):
    # Configure logging stream handlers according to the arguments.
    class StdoutFilter(logging.Filter):
        def filter(self, record):
            return record.levelno in (logging.DEBUG, logging.INFO)

    log.handlers = []

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.WARNING)
    stdout_handler.addFilter(StdoutFilter())
    if conf.debug:
        stdout_handler.setLevel(logging.DEBUG)
    elif conf.verbose:
        stdout_handler.setLevel(logging.INFO)
    else:
        stdout_handler.setLevel(logging.WARNING)
    log.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    msg_format = "%(levelname)s: %(message)s"
    stderr_handler.setFormatter(logging.Formatter(fmt=msg_format))
    stderr_handler.setLevel(logging.WARNING)
    log.addHandler(stderr_handler)
