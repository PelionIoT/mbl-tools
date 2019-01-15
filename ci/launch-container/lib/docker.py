#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Docker helper functions."""

import subprocess
import os


def build(*args):
    """Run the docker build command with args."""
    subprocess.Popen(["docker", "build", *args]).wait()


def run(*args):
    """Run the docker run command with args."""
    subprocess.Popen(["docker", "run", *args]).wait()


def cp(*args):
    """Run the docker cp command with args."""
    subprocess.Popen(["docker", "cp", *args]).wait()


def rm(*args):
    """Run the docker rm command with args."""
    subprocess.Popen(["docker", "rm", *args]).wait()
