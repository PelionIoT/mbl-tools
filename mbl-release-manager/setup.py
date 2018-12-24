#!/usr/bin/env python3
# Copyright (c) 2018 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""setup.py file for Mbed Linux OS Release Manager package."""

import os
from setuptools import setup


def read(fname):
    """Utility function to read the README file."""
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="mbl-release-manager",
    version="1",
    description="Mbed Linux OS Release Manager",
    long_description=read("README.md"),
    author="Arm Ltd.",
    license="BSD-3-Clause",
    install_requires=["in-place", "gitpython"],
    py_modules=["release_manager", "repo_manifest", "git_handler", "cli"],
    zip_safe=False,
    entry_points={"console_scripts": ["mbl-release-manager = cli:_main"]},
)
