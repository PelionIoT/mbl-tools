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

    args, _ = parser.parse_known_args()
    file_util.ensure_is_directory(args.builddir)
    file_util.ensure_is_directory(args.outputdir)
    return args


def main():
    """Script entry point."""
    args = _parse_args()

    # Set tup the Bitbake environemnt
    bitbake = Bitbake(
        builddir=args.builddir,
        outputdir=args.outputdir,
        machine=args.machine,
        distro=args.distro,
    )
    bitbake.setup_environment()

    # Build the packages
    packagess = "virtual/atf optee-os virtual/bootloader virtual/kernel"
    bitbake_build_commands = [
        "bitbake -c cleansstate {}".format(packages),
        "bitbake {}".format(packages),
    ]
    bitbake.run_commands(bitbake_build_commands)

    # Create the payloads
    create_update_payload_commands = [
        "create-update-payload -b1 -o {}/wks_bootloader1_payload.tar".format(
            args.outputdir
        ),
        "create-update-payload -b2 -o {}/wks_bootloader2_payload.tar".format(
            args.outputdir
        ),
        "create-update-payload -k -o {}/kernel_payload.tar".format(
            args.outputdir
        ),
    ]
    bitbake.run_commands(create_update_payload_commands)


if __name__ == "__main__":
    sys.exit(main())
