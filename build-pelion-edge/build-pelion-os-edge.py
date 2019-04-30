#!/usr/bin/env python3

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Script to create and build a pelion-os-edge workarea.

The pelion-os-edge project already contains a Makefile that creates and runs a
container to build the workarea. Therefore, this script:
    * Creates and initializes a pelion-os-edge workarea.
    * Makes some configuration tweaks.
    * Runs the provided Makefile to kick off a build.
"""

import argparse
import os
import shutil
import subprocess

import file_util

DEFAULT_MANIFEST_REPO = (
    "ssh://git@github.com/armPelionEdge/manifest-pelion-os-edge"
)


def _create_workarea(workdir, manifest_repo, branch):
    subprocess.run(
        ["repo", "init", "-u", manifest_repo, "-b", branch],
        cwd=workdir,
        check=True,
    )
    subprocess.run(["repo", "sync", "-j", "16"], cwd=workdir, check=True)


def _build(workdir):
    """
    Kick off a build of the workarea.

    This uses pelion-os-edge's helper Makefile to create a build container and
    start the build in that container.
    """
    subprocess.run(
        ["make"], cwd=os.path.join(workdir, "build-env"), check=True
    )


def _inject_mcc(workdir, path):
    """Add Mbed Cloud Client credentials into the build."""
    shutil.copy(path, os.path.join(workdir, "build-env"))


def _set_up_ssh(workdir):
    """Add support for using ssh-agent to access SSH keys during the build."""
    # This commit is to pass the SSH_AUTH_SOCK env var into the build container
    # and to mount the actual socket specified by SSH_AUTH_SOCK in the
    # container
    subprocess.run(
        ["git", "cherry-pick", "1245e2464424ed5baafe04a43ba03d97d7196e68"],
        cwd=os.path.join(workdir, "build-env"),
        check=True,
    )

    localconf_path = os.path.join(
        workdir, "poky", "meta-pelion-os-edge", "conf", "local.conf.sample"
    )

    # Add some BitBake config to allow BitBake tasks to read the SSH_AUTH_SOCK
    with file_util.replace_section_in_file(
        path=localconf_path, section_name="SSH support", comment_leader="#"
    ) as localconf:
        localconf.write("export SSH_AUTH_SOCK\n")
        localconf.write('BB_HASHBASE_WHITELIST_append = " SSH_AUTH_SOCK"\n')
        localconf.write('BB_HASHCONFIG_WHITELIST_append = " SSH_AUTH_SOCK"\n')


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--builddir",
        metavar="DIR",
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
        help="add a cloud client credentials file to the build",
        default=[],
        action="append",
    )

    args = parser.parse_args()

    file_util.ensure_is_directory(args.builddir)

    for path in args.inject_mcc:
        file_util.ensure_is_regular_file(path)

    return args


def main():
    """Script entry point."""
    args = _parse_args()

    _create_workarea(
        workdir=args.builddir,
        manifest_repo=args.manifest_repo,
        branch=args.branch,
    )

    for path in args.inject_mcc:
        _inject_mcc(args.builddir, path)

    _set_up_ssh(args.builddir)
    _build(args.builddir)


main()
