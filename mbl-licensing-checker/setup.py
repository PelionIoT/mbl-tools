# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""setup.py file for Mbed Linux OS repositories licensing checker application.
"""

import os
from setuptools import setup


def read(fname):
    """Utility function to read the README file."""
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="mbl-licensing-checker",
    version="1.0.0",
    description="MBL repo licensing checker application",
    long_description=read("README.md"),
    author="Arm Ltd.",
    license="BSD-3-Clause",
    packages=["mbl_licensing_checker"],
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "mbl-licensing-checker = \
            mbl_licensing_checker.cli:main"
        ]
    },
)
