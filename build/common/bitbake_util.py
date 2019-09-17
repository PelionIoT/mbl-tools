#!/usr/bin/env python3
# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Provides utilities for running commands in a bitbake environment."""

import sys
from pathlib import Path
from shutil import copy2, copytree

from pexpect.replwrap import bash


class BitbakeInvalidEnvironment(Exception):
    """Class for errors where an invalid environment is found."""

    def __init__(self, obj):
        """
        Initialize an object of this class.

        Args:
        * obj (PathLike): the path that doesn't exist or invalid

        """
        super().__init__("{} doesn't exist or invalid.".format(obj))


class Bitbake(object):
    """Class for creating the Bitbake environment."""

    def __init__(
        self,
        builddir,
        outputdir,
        machine,
        distro,
        init_env_file="setup-environment",
        env_variables=None,
    ):
        """
        Initialize an object of this class.

        Args:
        * builddir (str): base Bitbake build directory
        * outputdir (str): directory where to save artifacts
        * machine (str): Bitbake machine
        * distro (str): Bitbake distribution
        * init_env_file (str): initialization environment file
        * env_variables (dict): the dictionary specified the environment
                                variables to pass to the Bitbake init file

        """
        self.builddir = Path(builddir)
        self.outputdir = Path(outputdir)
        self.machine = machine
        self.distro = distro
        self.init_env_file = init_env_file
        self.env_variables = env_variables
        self.shell = bash()
        self._check_environment()

    def setup_environment(self):
        """Set up the Bitbake environment."""
        self.run_command("cd {}".format(self.builddir))
        env_vars = self._build_env_variables_string()
        command = "{} MACHINE={} . {} build-{}".format(
            env_vars, self.machine, self.init_env_file, self.distro
        )
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
        output = self.shell.run_command(command, timeout=timeout, async_=False)
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

    def save_artifacts(self, *files):
        """
        Copy *files into self.outputdir directory.

        Mandatory args:
        * files (str arguments): the list specifies files/directory to be
                                 copied into self.output directory


        If a file/directory is not found, it will be skipped and it continues
        to copy the next ones.

        """
        for obj in files:
            obj_path = self.builddir / obj
            if obj_path.exists():
                if obj_path.is_file():
                    copy2(obj_path, self.outputdir)
                elif obj_path.is_dir():
                    copytree(obj_path, self.outputdir / obj_path.name)
                else:
                    print(
                        "{}: file type not recognised. Skipping.".format(
                            obj_path
                        ),
                        file=sys.stderr,
                    )
            else:
                print("{} doesn't exists. Skipping.".format(obj_path))

    # Private methods
    def _check_environment(self):
        repo_dir = self.builddir / ".repo"
        if not repo_dir.exists() or not repo_dir.is_dir():
            raise BitbakeInvalidEnvironment(repo_dir)
        if not self.outputdir.exists() or not self.outputdir.is_dir():
            raise BitbakeInvalidEnvironment(self.outputdir)
        init_env_file_path = self.builddir / self.init_env_file
        if not init_env_file_path.exists() or not init_env_file_path.is_file():
            raise BitbakeInvalidEnvironment(init_env_file_path)

    def _build_env_variables_string(self):
        string = ""
        if isinstance(self.env_variables, dict):
            str = " ".join(
                "{}={}".format(key, value) for key, value in self.env_variables
            )
        return string
