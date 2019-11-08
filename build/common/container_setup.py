#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Tools for initializing build containers."""

import argparse
import pathlib
import subprocess

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent


def set_up_container(extra_ssh_hosts=[]):
    """Initialize a build container."""
    set_up_git()
    set_up_ssh(extra_ssh_hosts)


def set_up_git():
    """Initialize a sane git setup."""
    subprocess.run([str(SCRIPTS_DIR / "git-setup.sh")], check=True)


def set_up_ssh(extra_ssh_hosts=[]):
    """Initialize a sane SSH setup."""
    subprocess.run(
        [str(SCRIPTS_DIR / "ssh-setup.sh")] + extra_ssh_hosts, check=True
    )


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-host",
        dest="extra_ssh_hosts",
        metavar="HOST",
        action="append",
        help=(
            "Add a trusted git repository host to the build environment."
            " Can be specified multiple times."
        ),
        default=[],
    )
    args, _ = parser.parse_known_args()
    return args


def main(args):
    """Script entry point."""
    set_up_container(extra_ssh_hosts=args.extra_ssh_hosts)
    return 0


if __name__ == "__main__":
    sys.exit(main(_parse_args()))
