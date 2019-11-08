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
import warnings
import tarfile

from container_setup import set_up_container
import file_util

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent

DEFAULT_MANIFEST_REPO = (
    "ssh://git@github.com/armPelionEdge/manifest-pelion-os-edge"
)

DEFAULT_IMAGE = "console-image"

TMP_DIR_NAME = "tmp-glibc"


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
    sys.stderr.flush()


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


def _build(workdir, image):
    """
    Kick off a build of the image in the workarea.

    Args:
    * workdir (Path): top level of work area.

    """
    subprocess.run(
        [SCRIPTS_DIR / "bitbake-wrapper.sh", workdir, image], check=True
    )


def _save_artifacts(workdir, outputdir, image):
    """
    Save artifacts to the output directory.

    Args:
    * workdir (Path): top level of work area.
    * outputdir (Path): output directory where to save artifacts.

    """
    if outputdir:
        # Save artifact from deploy/images directory
        shutil.copytree(
            workdir / "poky" / image / TMP_DIR_NAME / "deploy" / "images",
            outputdir / "images",
            symlinks=True,
            ignore=shutil.ignore_patterns("*.cpio.gz", "*.wic"),
        )

        # Save licenses info from deploy/licenses directory
        licenses_path = (
            workdir / "poky" / image / TMP_DIR_NAME / "deploy" / "licenses"
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


def _inject_mcc(workdir, path):
    """
    Add Upgrade and Mbed Cloud Client credentials into the build.

    Args:
    * workdir (Path): top level of work area.
    * path (Path): path to file to inject into build.

    """
    name = pathlib.Path(path).name
    print("Injecting mcc: {}".format(pathlib.Path(path).name), flush=True)
    if name == "upgradeCA.cert":
        shutil.copy(
            path,
            workdir
            / "poky"
            / "meta-pelion-edge"
            / "recipes-core"
            / "ww-console-image-initramfs-init"
            / "files",
        )
    else:
        shutil.copy(
            path,
            workdir
            / "poky"
            / "meta-pelion-edge"
            / "recipes-wigwag"
            / "mbed-edge-core"
            / "files",
        )


def _inject_key(workdir, path, image):
    """
    Add keys into the build.

    Args:
    * workdir (Path): top level of work area.
    * path (Path): path to file to inject into build.

    """
    name = pathlib.Path(path).name
    print("Injecting key: {}".format(name), flush=True)
    if name == "rot_key.pem":
        pathlib.Path(
            "{}/poky/meta-pelion-edge/recipes-bsp/atf/files".format(workdir)
        ).mkdir(parents=True, exist_ok=True)
        shutil.copy(
            path,
            workdir
            / "poky"
            / "meta-pelion-edge"
            / "recipes-bsp"
            / "atf"
            / "files",
        )
    else:
        pathlib.Path("{}/poky/{}".format(workdir, image)).mkdir(
            parents=True, exist_ok=True
        )
        shutil.copy(path, workdir / "poky" / image)


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
        workdir / "poky" / "meta-pelion-edge" / "conf" / "local.conf.sample"
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
        "--manifest-repo",
        metavar="REPO",
        help=(
            "manifest repo to use. Default is "
            '"{}"'.format(DEFAULT_MANIFEST_REPO)
        ),
        default=DEFAULT_MANIFEST_REPO,
    )
    parser.add_argument(
        "--image",
        metavar="STRING",
        help="bitbake image to build",
        default=DEFAULT_IMAGE,
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
        "--inject-key",
        metavar="FILE",
        type=_str_to_resolved_path,
        help="add key or certificate to the build",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--downloaddir",
        metavar="PATH",
        type=_str_to_resolved_path,
        help="directory used for BitBake's download cache (sets DL_DIR)",
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

    args, unknown = parser.parse_known_args()

    if len(unknown) > 0:
        warning("unsupported arguments: {}".format(unknown))

    if len(args.inject_mcc) < 3:
        print(
            "build.py: error: 3 of the following arguments are required: "
            "--inject-mcc"
        )
        print(
            "expecting - upgradeCA.cert, mbed_cloud_dev_credentials.c & "
            "update_default_resources.c"
        )
        print(
            "  E.g. - manifest-tool cert create -C UK -S CAMBS -L Cambridge "
            "-O arm.com -U arm -V 90 -K upgradeCA.key -o upgradeCA.cert"
        )
        print(
            "  E.g. - https://os.mbed.com/docs/mbed-linux-os/v0.5/"
            "getting-started/preparing-device-management-sources.html"
        )
        exit(2)

    if len(args.inject_key) < 3:
        print(
            "build.py: error: 3 of the following arguments are required: "
            "--inject-key"
        )
        print(
            "expecting - rot_key.pem, mbl-fit-rot-key.key & "
            "mbl-fit-rot-key.crt"
        )
        print("  E.g. - openssl genrsa 2048 > boot-keys/rot_key.pem")
        print("  E.g. - openssl genrsa 2048 > boot-keys/mbl-fit-rot-key.key")
        print(
            "  E.g. - openssl req -batch -new -x509 -key "
            "boot-keys/mbl-fit-rot-key.key > boot-keys/mbl-fit-rot-key.crt"
        )
        exit(2)

    file_util.ensure_is_directory(args.builddir)

    for path in args.inject_mcc:
        file_util.ensure_is_regular_file(path)

    return args


def main():
    """Script entry point."""
    warnings.formatwarning = warning_on_one_line

    args = _parse_args()
    set_up_container()
    _set_up_download_dir(args.downloaddir)

    _create_workarea(
        workdir=args.builddir,
        manifest_repo=args.manifest_repo,
        branch=args.branch,
    )

    for path in args.inject_mcc:
        _inject_mcc(args.builddir, path)
    for path in args.inject_key:
        _inject_key(args.builddir, path, args.image)

    _set_up_bitbake_ssh(args.builddir)
    _build(args.builddir, args.image)
    _save_artifacts(args.builddir, args.outputdir, args.image)


if __name__ == "__main__":
    sys.exit(main())
