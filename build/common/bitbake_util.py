#!/usr/bin/env python3
# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Provides utilities for running commands in a bitbake environment."""

import os
from pathlib import Path
from shlex import quote
import subprocess
import sys


class BitbakeError(Exception):
    """Base class for errors relating to the Bitbake environment."""

    pass


class BitbakeInvalidDirectoryError(BitbakeError):
    """Class for errors where an invalid directory is found."""

    def __init__(self, obj):
        """
        Initialize an object of this class.

        Args:
        * obj (PathLike): the path that doesn't exist or invalid

        """
        super().__init__(
            "Directory {} doesn't exist or invalid."
            "Please specify a valid Bitbake build directory".format(obj)
        )


class BitbakeInvalidFileError(BitbakeError):
    """Class for errors where an invalid file is found."""

    def __init__(self, obj):
        """
        Initialize an object of this class.

        Args:
        * obj (PathLike): the path that doesn't exist or invalid

        """
        super().__init__("File {} doesn't exist or invalid.".format(obj))


class Bitbake(object):
    """Class for creating the Bitbake environment."""

    def __init__(
        self, builddir, machine, distro, init_env_file="setup-environment"
    ):
        """
        Initialize an object of this class.

        Args:
        * builddir (PathLike): base Bitbake build directory
        * machine (str): Bitbake machine
        * distro (str): Bitbake distribution
        * init_env_file (str): initialization environment file

        """
        self.builddir = builddir
        self.machine = machine
        self.distro = distro
        self.init_env_file = init_env_file
        self._validate_parameters()
        self._check_environment()

    def _generate_setup_env_command(self):
        """Generate a Bash command to set up the BitBake environment."""
        return ". {} build-{}".format(
            quote(self.init_env_file), quote(self.distro)
        )

    def run_command(self, command, **kwargs):
        """
        Run a command in the Bitbake environment.

        Runs a command within the BitBake environment using subprocess.run().
        Most of the subprocess.run options can be used with run_command() and
        have the same meanings. The exceptions are:
        * shell: The command is always executed in a Bash shell and must be
          given as a string rather than a list. The shell option is ignored.
        * env: The env option works like it does in subprocess.run(), except
          that the MACHINE and DISTRO environment variables will also be in the
          environment, along with any that setup-environment sets.
        * cwd: If cwd is not given then the command is run from the BitBake
          build directory. If cwd is given and it is a relative path then it
          will be interpreted relative to the BitBake build directory.

        Mandatory args:
        * command (str): the command to run in the environment

        Optional args:
        * kwargs for subprocess.run().

        Return:
        * subprocess.CompletedProcess object.

        """
        # setup-environment will change the current directory to the BitBake
        # build dir when it is run, so if the user wants to run a command from
        # somewhere else then we need to handle that after setup-environment
        # runs. We can't do that with subprocess.run()'s "cwd" option so add a
        # "cd" command after sourcing setup-environment.
        cd_command = ""
        if kwargs.get("cwd"):
            cd_command = "cd {} &&".format(quote(str(kwargs["cwd"])))

        full_command = "{} && {} {}".format(
            self._generate_setup_env_command(), cd_command, command
        )

        print('Running "{}"...'.format(full_command))

        # Flush stdout and stderr before calling the subprocess so that the
        # subprocess's output can't appear before prints we've already done.
        # This is more noticable when stdout and/or stderr are redirected to
        # files - they are block-buffered rather than line-buffered in that
        # case (yes, even stderr on at least some versions of Python!).
        sys.stdout.flush()
        sys.stderr.flush()

        # Don't modify the caller's dict
        kwargs = kwargs.copy()

        kwargs["shell"] = False
        kwargs["cwd"] = str(self.top_dir)
        if "env" in kwargs:
            kwargs["env"] = kwargs["env"].copy()
        else:
            kwargs["env"] = os.environ.copy()
        kwargs["env"]["MACHINE"] = self.machine
        kwargs["env"]["DISTRO"] = self.distro
        ret = subprocess.run(["bash", "-c", full_command], **kwargs)
        print("Command finished with exit code {}".format(ret.returncode))
        return ret

    def _check_environment(self):
        self.top_dir = (
            self.builddir / "machine-{}".format(self.machine) / "mbl-manifest"
        )
        repo_dir = self.top_dir / ".repo"
        if not repo_dir.exists() or not repo_dir.is_dir():
            raise BitbakeInvalidDirectoryError(repo_dir)
        init_env_file_path = self.top_dir / self.init_env_file
        if not init_env_file_path.exists() or not init_env_file_path.is_file():
            raise BitbakeInvalidFileError(init_env_file_path)

    def _validate_parameters(self):
        # mandatory parameters
        assert isinstance(self.builddir, Path) and self.builddir
        assert isinstance(self.machine, str) and self.machine
        assert isinstance(self.distro, str) and self.distro
        assert isinstance(self.init_env_file, str) and self.init_env_file
