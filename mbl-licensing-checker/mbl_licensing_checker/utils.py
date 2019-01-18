# Based on: src/pydocstyle/utils.py
# In open-source project: https://github.com/PyCQA/pydocstyle
#
# Original file: Copyright (c) 2014-2017 Amir Rachum, <http://amir.rachum.com/>
# Modifications: Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: MIT
"""Contains utilities."""

import logging
import re

__version__ = "1.0.0"
log = logging.getLogger(__name__)


def is_blank(string):
    """Return True iff the string contains only whitespaces."""
    return not string.strip()


def find_pattern(lines, pattern):
    """Return a match group if the pattern is found otherwise return None."""
    for line in lines:
        match = pattern.search(line)
        if match:
            return match.group
