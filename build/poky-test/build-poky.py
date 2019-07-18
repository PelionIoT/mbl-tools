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

DEFAULT_MANIFEST_REPO = "ssh://git@github.com/ARMmbed/mbl-manifest"

DEFAULT_MANIFEST_XML = "poky.xml"


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
        cwd=str(workdir),
        check=True,
    )
    subprocess.run(["repo", "sync", "-j", "16"], cwd=str(workdir), check=True)


def _add_bitbake_layers(workdir):
    """
    Add the necessary bitbake layers.

    Args:
    * workdir (Path): top level of work area.

    """
    layer_command = "bitbake-layers add-layer "

    subprocess.run(
        [
            str(SCRIPTS_DIR / "poky-bitbake-wrapper.sh"),
            str(workdir),
            "bitbake-layers",
            "add-layer",
            "../../meta-freescale",
        ],
        check=True,
    )

    subprocess.run(
        [
            str(SCRIPTS_DIR / "poky-bitbake-wrapper.sh"),
            str(workdir),
            "bitbake-layers",
            "add-layer",
            "../../meta-mbl/meta-psa/",
        ],
        check=True,
    )


def _build(workdir, image):
    """
    Kick off a build of the workarea.

    Args:
    * workdir (Path): top level of work area.

    """

    subprocess.run(
        [
            str(SCRIPTS_DIR / "poky-bitbake-wrapper.sh"),
            str(workdir),
            "bitbake",
            image,
        ],
        check=True,
    )


def _save_artifacts(workdir, outputdir, machine, image):
    """
    Save artifacts to the output directory.

    Args:
    * workdir (Path): top level of work area.
    * outputdir (Path): output directory where to save artifacts.

    """
    if outputdir:
        # Save artifact from deploy/images directory
        shutil.copytree(
            str(
                workdir
                / "layers"
                / "poky"
                / "build"
                / "tmp"
                / "deploy"
                / "images"
                / machine
            ),
            str(outputdir / "machine" / machine / "images" / image / "images"),
            symlinks=True,
            ignore=shutil.ignore_patterns("*.cpio.gz", "*.wic"),
        )

        # Save licenses info from deploy/licenses directory
        licenses_path = (
            workdir
            / "layers"
            / "poky"
            / "build"
            / "tmp"
            / "deploy"
            / "licenses"
        )
        output_license_file = outputdir / "licenses.tar.gz"
        with tarfile.open(str(output_license_file), "w:gz") as tar:
            tar.add(str(licenses_path), arcname=licenses_path.name)

        # Save the manifest file from .repo/manifests
        shutil.copy(
            str(workdir / ".repo" / "manifests" / "default.xml"),
            str(outputdir / "manifest.xml"),
        )
    else:
        warning("--outputdir not specified. Not saving artifacts.")


def _set_up_git():
    """Initialize a sane git setup."""
    subprocess.run([str(SCRIPTS_DIR / "git-setup.sh")], check=True)


def _set_up_container_ssh():
    """Initialize a sane SSH setup."""
    subprocess.run([str(SCRIPTS_DIR / "ssh-setup.sh")], check=True)


def _set_up_bitbake_machine(workdir, machine):
    """
    Configure BitBake to build the selected machine.

    Args:
    * workdir (Path): top level of work area.

    """
    localconf_path = (
        workdir
        / "layers"
        / "poky"
        / "meta-poky"
        / "conf"
        / "local.conf.sample"
    )

    # Add some BitBake config to allow BitBake tasks build the right thing
    with file_util.replace_section_in_file(
        path=localconf_path, section_name="MACHINE ??", comment_leader="#"
    ) as localconf:
        localconf.write('MACHINE ?= "{}"\n'.format(machine))
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
    return pathlib.Path(path_str).resolve()


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
    parser.add_argument(
        "--accept-eula",
        metavar="STRING",
        help="Automatically accept any EULAs required for building MACHINE",
        required=False,
    )
    parser.add_argument(
        "--machine",
        metavar="STRING",
        help="Machine to build. The only supported machine is imxmmevk",
        required=False,
        default="imx8mmevk",
    )
    parser.add_argument(
        "--build-tag",
        metavar="STRING",
        help="Specify a unique version tag to identify the build.",
        required=False,
    )
    parser.add_argument(
        "--jobs",
        "-j",
        metavar="STRING",
        help="Set the number of parallel processes. "
        "Default # CPU on the host.",
        required=False,
    )
    parser.add_argument(
        "-x",
        action="store_true",
        help="Enable debugging. Currently ignored.",
        required=False,
    )
    parser.add_argument(
        "--artifactory-api-key",
        metavar="STRING",
        help="Artifactory API key. Currently ignored.",
        required=False,
    )
    parser.add_argument(
        "--image",
        metavar="STRING",
        help="Name of the image to build.",
        default="core-image-minimal",
        required=False,
    )

    args = parser.parse_args()

    file_util.ensure_is_directory(args.builddir)

    return args


def main():
    """Script entry point."""
    warnings.formatwarning = warning_on_one_line

    args = _parse_args()

    if args.machine != "imx8mmevk":
        print(
            "ERROR: The only supported machine is imx8mmevk. "
            "The selected machine is {}".format(args.machine)
        )
        sys.exit(1)

    _set_up_container_ssh()
    _set_up_git()
    _set_up_download_dir(args.downloaddir)

    _create_workarea(
        workdir=args.builddir,
        manifest_repo=args.manifest_repo,
        branch=args.branch,
        manifest=args.manifest,
    )

    _set_up_bitbake_machine(args.builddir, args.machine)

    _add_bitbake_layers(args.builddir)

    _build(args.builddir, args.image)
    _save_artifacts(args.builddir, args.outputdir, args.machine, args.image)


if __name__ == "__main__":
    sys.exit(main())
