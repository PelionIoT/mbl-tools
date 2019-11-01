#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Script to build BL2, BL3 and fitImage and create the update payloads.

The script uses the bitbake_util module to run custom commands in a
preexistent bitbake environemnt.
"""
import sys
import argparse

import file_util
from bitbake_util import Bitbake
from container_setup import set_up_container


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--builddir",
        metavar="DIR",
        type=file_util.str_to_resolved_path,
        help="directory in which to build",
        required=True,
    )
    parser.add_argument(
        "--outputdir",
        metavar="PATH",
        type=file_util.str_to_resolved_path,
        help="directory in which to place build artifacts",
        required=True,
    )
    parser.add_argument(
        "--machine", metavar="STRING", help="Machine to build.", required=True
    )
    parser.add_argument(
        "--distro",
        metavar="STRING",
        help="Name of the distro to build.",
        default="mbl-development",
        required=False,
    )
    parser.add_argument(
        "--image",
        metavar="STRING",
        help="Name of the image to build.",
        default="mbl-image-development",
        required=False,
    )
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
    file_util.ensure_is_directory(args.builddir)
    file_util.ensure_is_directory(args.outputdir)
    return args


def main():
    """Script entry point."""
    args = _parse_args()

    set_up_container(extra_ssh_hosts=args.extra_ssh_hosts)

    # Set up the Bitbake environemnt
    bitbake = Bitbake(
        builddir=args.builddir, machine=args.machine, distro=args.distro
    )

    # Build the packages
    packages = "virtual/atf optee-os virtual/bootloader virtual/kernel"
    bitbake_build_commands = [
        "bitbake -c cleansstate {}".format(packages),
        "bitbake {}".format(args.image),
    ]
    for command in bitbake_build_commands:
        bitbake.run_command(command, check=True, verbose=True)

    # Create the payloads
    bootloader1_base_path = args.outputdir / "bootloader1_payload"
    bootloader2_base_path = args.outputdir / "bootloader2_payload"
    kernel_base_path = args.outputdir / "kernel_payload"
    rootfs_base_path = args.outputdir / "rootfs_payload"

    create_update_payload_commands = [
        "create-update-payload -b1 -o {0}.swu -t {0}.testinfo".format(
            bootloader1_base_path
        ),
        "create-update-payload -b2 -o {0}.swu -t {0}.testinfo".format(
            bootloader2_base_path
        ),
        "create-update-payload -k -o {0}.swu -t {0}.testinfo".format(
            kernel_base_path
        ),
        "create-update-payload -r {0} -o {1}.swu -t {1}.testinfo".format(
            args.image, rootfs_base_path
        ),
    ]
    for command in create_update_payload_commands:
        bitbake.run_command(command, check=True, verbose=True)


if __name__ == "__main__":
    sys.exit(main())
