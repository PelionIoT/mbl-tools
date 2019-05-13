#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Script to create and build a pelion-os-edge workarea inside a container.

This script:
    * Sets up SSH and Git in the container.
    * Creates and initializes a pelion-os-edge workarea.
    * Adds Pelion Device Management credentials to the workarea.
    * Makes some configuration tweaks.
    * Builds a pelion-os-edge image.

The pelion-os-edge project already contains a Makefile that creates and runs a
container to build the workarea. This script is already running in a container
though, so to avoid having nested containers, we won't use pelion-os-edge's
Makefile, we'll run BitBake directly.
"""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

import file_util

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent

DEFAULT_MANIFEST_REPO = (
    "ssh://git@github.com/armPelionEdge/manifest-pelion-os-edge"
)


def _create_workarea(workdir, manifest_repo, branch):
    """
    Download repos required for pelion-os-edge build.

    Args:
    * workdir (Path): top level of work area.
    * manfiest_repo (str): URI of repo containing the project manifest.
    * branch (str): branch of repo containing the project manifest.
    """
    subprocess.run(
        ["repo", "init", "-u", manifest_repo, "-b", branch],
        cwd=workdir,
        check=True,
    )
    subprocess.run(["repo", "sync", "-j", "16"], cwd=workdir, check=True)


def _build(workdir):
    """
    Kick off a build of the workarea.

    Args:
    * workdir (Path): top level of work area.
    """
    subprocess.run(
        [
            SCRIPTS_DIR / "pelion-os-edge-bitbake-wrapper.sh",
            workdir,
            "console-image",
        ],
        check=True,
    )


def _inject_mcc(workdir, path):
    """
    Add Mbed Cloud Client credentials into the build.

    Args:
    * workdir (Path): top level of work area.
    * path (Path): path to file to inject into build.

    """
    shutil.copy(
        path,
        workdir
        / "poky"
        / "meta-pelion-os-edge"
        / "recipes-wigwag"
        / "mbed-edge-core"
        / "files",
    )


def _set_up_git():
    """Initialize a sane git setup."""
    subprocess.run([SCRIPTS_DIR / "git-setup.sh"], check=True)


def _set_up_container_ssh():
    """Initialize a sane SSH setup."""
    subprocess.run([SCRIPTS_DIR / "ssh-setup.sh"], check=True)


def _set_up_bitbake_ssh(workdir):
    """
    Configure BitBake to allow use of ssh-agent.

    Args:
    * workdir (Path): top level of work area.
    """
    localconf_path = (
        workdir / "poky" / "meta-pelion-os-edge" / "conf" / "local.conf.sample"
    )

    # Add some BitBake config to allow BitBake tasks to read the SSH_AUTH_SOCK
    with file_util.replace_section_in_file(
        path=localconf_path, section_name="SSH support", comment_leader="#"
    ) as localconf:
        localconf.write("export SSH_AUTH_SOCK\n")
        localconf.write('BB_HASHBASE_WHITELIST_append = " SSH_AUTH_SOCK"\n')
        localconf.write('BB_HASHCONFIG_WHITELIST_append = " SSH_AUTH_SOCK"\n')


def _set_up_download_dir(download_dir):
    """
    Set the directory used for BitBake's downloads.

    Args:
    * download_dir (Path): directory to use for BitBake's downloads.
    """
    if not download_dir:
        return

    os.environ["DL_DIR"] = str(pathlib.Path(download_dir).resolve())


def _str_to_resolved_path(path_str):
    """
    Convert a string to a resolved Path object.

    Args:
    * path_str (str): string to convert to a Path object.
    """
    return pathlib.Path(path_str).resolve(strict=False)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--builddir",
        metavar="DIR",
        type=_str_to_resolved_path,
        help="directory in which to build",
        required=True,
    )
    parser.add_argument(
        "--branch",
        metavar="BRANCH",
        help="branch of the manifest repo to use",
        required=True,
    )
    parser.add_argument(
        "--manifest-repo",
        metavar="REPO",
        help=(
            "manifest repo to use. Default is "
            '"{}"'.format(DEFAULT_MANIFEST_REPO)
        ),
        default=DEFAULT_MANIFEST_REPO,
    )
    parser.add_argument(
        "--inject-mcc",
        metavar="FILE",
        type=_str_to_resolved_path,
        help="add a cloud client credentials file to the build",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--downloaddir",
        metavar="PATH",
        type=_str_to_resolved_path,
        help="directory used for BitBake's download cache (currently ignored)",
        required=False,
    )
    parser.add_argument(
        "--outputdir",
        metavar="PATH",
        type=_str_to_resolved_path,
        help="directory in which to place build artifacts",
        required=False,
    )
    parser.add_argument(
        "--parent-command-line",
        metavar="STRING",
        help=(
            "Specify the command line that was used to invoke the"
            "script that invokes build.sh."
        ),
        required=False,
    )
    parser.add_argument(
        "--mbl-tools-version",
        metavar="STRING",
        help="Specify the version of mbl-tools that this script came from.",
        required=False,
    )

    args = parser.parse_args()

    file_util.ensure_is_directory(args.builddir)

    for path in args.inject_mcc:
        file_util.ensure_is_regular_file(path)

    return args


def main():
    """Script entry point."""
    args = _parse_args()
    _set_up_container_ssh()
    _set_up_git()
    _set_up_download_dir(args.downloaddir)

    _create_workarea(
        workdir=args.builddir,
        manifest_repo=args.manifest_repo,
        branch=args.branch,
    )

    for path in args.inject_mcc:
        _inject_mcc(args.builddir, path)

    _set_up_bitbake_ssh(args.builddir)
    _build(args.builddir)


if __name__ == "__main__":
    sys.exit(main())
