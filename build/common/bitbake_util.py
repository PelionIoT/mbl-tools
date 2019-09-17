#!/usr/bin/env python3
# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Provides utilities for running commands in a bitbake environment."""

import sys
from pathlib import Path
from shlex import quote

from pexpect.replwrap import bash


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
            "Please specify a valid build Bitbake directory".format(obj)
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
        self,
        builddir,
        machine,
        distro,
        init_env_file="setup-environment",
        env_variables=None,
    ):
        """
        Initialize an object of this class.

        Args:
        * builddir (PathLike): base Bitbake build directory
        * machine (str): Bitbake machine
        * distro (str): Bitbake distribution
        * init_env_file (str): initialization environment file
        * env_variables (dict): the dictionary specified the environment
                                variables to pass to the Bitbake init file

        """
        self.builddir = builddir
        self.machine = machine
        self.distro = distro
        self.init_env_file = init_env_file
        self.env_variables = env_variables
        self._shell = bash()
        self._validate_parameters()
        self._check_environment()

    def setup_environment(self):
        """Set up the Bitbake environment."""
        self.run_command("cd {}".format(quote(str(self.builddir))))
        env_vars = self._build_env_variables_string()
        if env_vars:
            env_vars = quote(env_vars)
        command = "{} MACHINE={} . {} build-{}".format(
            env_vars,
            quote(self.machine),
            quote(self.init_env_file),
            quote(self.distro),
        )
        print(command)
        self.run_command(command)

    def run_command(self, command, timeout=None, stdout=True):
        """
        Run a command in the Bitbake environment.

        Mandatory args:
        * command (str): the command to run in the environment

        Optional args:
        * timeout (int): how long to wait for the next prompt. None means to
                         wait indefinitely
        * stdout (bool): flag to print the output to stdout

        Return:
        * output (str): output of the specified command

        """
        output = self._shell.run_command(
            command, timeout=timeout, async_=False
        )
        if stdout:
            print(output)
        return output

    def run_commands(self, commands, timeout=None, stdout=True):
        """
        Run a list of commands in the Bitbake environment.

        Mandatory args:
        * commands (list): the commands to run in the environment

        Optional args:
        * timeout (int): how long to wait for the next prompt. None means to
                         wait indefinitely
        * stdout (bool): flag to print the output to stdout

        If a command fails its execution, it will continue executing the
        remaining commands.

        """
        for command in commands:
            self.run_command(command, timeout=timeout, stdout=stdout)

    def _build_env_variables_string(self):
        env_string = ""
        if self.env_variables is not None:
            env_string = " ".join(
                "{}={}".format(key, value)
                for key, value in self.env_variables.items()
            )
        return env_string

    def _check_environment(self):
        repo_dir = self.builddir / ".repo"
        if not repo_dir.exists() or not repo_dir.is_dir():
            raise BitbakeInvalidDirectoryError(repo_dir)
        init_env_file_path = self.builddir / self.init_env_file
        if not init_env_file_path.exists() or not init_env_file_path.is_file():
            raise BitbakeInvalidFileError(init_env_file_path)

    def _validate_parameters(self):
        # mandatory parameters
        assert isinstance(self.builddir, Path) and self.builddir
        assert isinstance(self.machine, str) and self.machine
        assert isinstance(self.distro, str) and self.distro
        # init_env_file should be always specified
        assert isinstance(self.init_env_file, str) and self.init_env_file
        # env_variables is optional
        assert isinstance(self.env_variables, dict)
