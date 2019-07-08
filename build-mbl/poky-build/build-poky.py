#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Script to create and build a poky workarea inside a container.

This script:
    * Sets up SSH and Git in the container.
    * Creates and initializes a poky workarea.
    * Makes some configuration tweaks.
    * Builds a poky image.

"""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import warnings
import tarfile

import file_util

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent

DEFAULT_MANIFEST_REPO = (
    "ssh://git@github.com/ARMmbed/mbl-manifest"
)

DEFAULT_MANIFEST_XML = (
    "poky.xml"
)


def warning_on_one_line(
    message, category, filename, lineno, file=None, line=None
):
    """Format a warning the standard way."""
    return "{}:{}: {}: {}\n".format(
        filename, lineno, category.__name__, message
    )


def warning(message):
    """
    Issue a UserWarning Warning.

    Args:
    * message: warning's message
    """
    warnings.warn(message, stacklevel=2)


def _create_workarea(workdir, manifest_repo, branch, manifest):
    """
    Download repos required for poky build.

    Args:
    * workdir (Path): top level of work area.
    * manfiest_repo (str): URI of repo containing the project manifest.
    * branch (str): branch of repo containing the project manifest.
    """
    subprocess.run(
        ["repo", "init", "-u", manifest_repo, "-b", branch, "-m", manifest],
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
    print(SCRIPTS_DIR)
    print(workdir)

    subprocess.run(
        [
            SCRIPTS_DIR / "poky-bitbake-wrapper.sh",
            workdir,
            "core-image-minimal",
        ],
        check=True,
    )


def _save_artifacts(workdir, outputdir):
    """
    Save artifacts to the output directory.

    Args:
    * workdir (Path): top level of work area.
    * outputdir (Path): output directory where to save artifacts.
    """
    if outputdir:
        # Save artifact from deploy/images directory
        shutil.copytree(
            workdir / "layers" / "poky" / "core-image-minimal" / "tmp" / "deploy" / "images",
            outputdir / "images",
            symlinks=True,
            ignore=shutil.ignore_patterns("*.cpio.gz", "*.wic"),
        )

        # Save licenses info from deploy/licenses directory
        licenses_path = (
            workdir / "layers" / "poky" / "core-image-minimal" / "tmp" / "deploy" / "licenses"
        )
        output_license_file = outputdir / "licenses.tar.gz"
        with tarfile.open(output_license_file, "w:gz") as tar:
            tar.add(licenses_path, arcname=licenses_path.name)

        # Save the manifest file from .repo/manifests
        shutil.copy(
            workdir / ".repo" / "manifests" / "default.xml",
            outputdir / "manifest.xml",
        )
    else:
        warning("--outputdir not specified. Not saving artifacts.")



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
        workdir / "layers" / "poky" / "meta-poky" / "conf" / "local.conf.sample"
    )

    # Add some BitBake config to allow BitBake tasks to read the SSH_AUTH_SOCK
    with file_util.replace_section_in_file(
        path=localconf_path, section_name="SSH support", comment_leader="#"
    ) as localconf:
        localconf.write("export SSH_AUTH_SOCK\n")
        localconf.write('BB_HASHBASE_WHITELIST_append = " SSH_AUTH_SOCK"\n')
        localconf.write('BB_HASHCONFIG_WHITELIST_append = " SSH_AUTH_SOCK"\n')

def _set_up_bitbake_machine(workdir):
    """
    Configure BitBake to build the selected machine 

    Args:
    * workdir (Path): top level of work area.
    """
    localconf_path = (
        workdir / "layers" / "poky" / "meta-poky" / "conf" / "local.conf.sample"
    )

    # Add some BitBake config to allow BitBake tasks build the right thing
    with file_util.replace_section_in_file(
        path=localconf_path, section_name="MACHINE ??", comment_leader="#"
    ) as localconf:
        localconf.write('MACHINE ?= "imx8mmevk"\n')
        localconf.write('ACCEPT_FSL_EULA = "1"\n')
        localconf.write('CORE_IMAGE_EXTRA_INSTALL += "mbed-crypto-test"\n')
        localconf.write('CORE_IMAGE_EXTRA_INSTALL += "psa-arch-tests"\n')




def _set_up_download_dir(download_dir):
    """
    Set the directory used for BitBake's downloads.

    Args:
    * download_dir (Path): directory to use for BitBake's downloads.
    """
    if download_dir:
        os.environ["DL_DIR"] = str(pathlib.Path(download_dir).resolve())
    else:
        warning("--downloaddir not specified. Not setting DL_DIR.")


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
        "--manifest",
        metavar="MANIFEST",
        help=(
            "manifest xml to use. Default is "
             '"{}"'.format(DEFAULT_MANIFEST_XML)
        ),
        default=DEFAULT_MANIFEST_XML,
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

    return args


def main():
    """Script entry point."""
    warnings.formatwarning = warning_on_one_line

    args = _parse_args()
    _set_up_container_ssh()
    _set_up_git()
    _set_up_download_dir(args.downloaddir)

    _create_workarea(
        workdir=args.builddir,
        manifest_repo=args.manifest_repo,
        branch=args.branch,
        manifest=args.manifest,
    )

    _set_up_bitbake_ssh(args.builddir)
    _set_up_bitbake_machine(args.builddir)

    _build(args.builddir)
    _save_artifacts(args.builddir, args.outputdir)


if __name__ == "__main__":
    sys.exit(main())
