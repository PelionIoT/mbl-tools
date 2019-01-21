# Based on: src/pydocstyle/config.py
# In open-source project: https://github.com/PyCQA/pydocstyle
#
# Original file: Copyright (c) 2014-2017 Amir Rachum, <http://amir.rachum.com/>
# Modifications: Copyright (c) 2019 Arm Limited and Contributors. All rights
#                reserved.
#
# SPDX-License-Identifier: MIT
"""Configuration file parsing and utilities."""

import argparse
import copy
import functools
import os
import re
from collections import namedtuple
from collections.abc import Set
from configparser import RawConfigParser

from .utils import __version__, log
from .violations import ErrorRegistry, conventions


class ConfigurationParser:
    """Responsible for parsing configuration from files and CLI.

    There are 2 types of configurations: Run configurations and Check
    configurations.

    Run Configurations:
    ------------------
    Responsible for deciding things that are related to the user interface and
    configuration discovery, e.g. verbosity, debug options, etc.
    All run configurations default to `False` or `None` and are decided only
    by CLI.

    Check Configurations:
    --------------------
    Configurations that are related to which files and licenses/copyrights will
    be checked. These are configurable in 2 ways: using the CLI, and using
    configuration files.

    Configuration files are nested within the file system, meaning that the
    close a configuration file is to a checked file, the more relevant it will
    be. For instance, imagine this directory structure:

    A
    +-- .mbl-licensing-checker: sets `convention=reuse_v2_0`
    +-- B
        +-- foo.py
        +-- .mbl-licensing-checker: sets `convention=none`

    The `foo.py` will not be checked for the convention`reuse_v2_0`.
    The configuration build algorithm is described in `self._get_config`.

    Note: If the convention argument was selected in the CLI,
    all configuration files will be ignored and each file will be checked for
    the error codes supplied in the CLI.

    """

    CONFIG_FILE_ARGUMENTS = (
        "convention",
        "add-select",
        "add-ignore",
        "match",
        "match-dir",
    )
    DEFAULT_MATCH_RE = r"(?!test_).*\.(bb|bbappend|bbclass|c|cpp|h|md|py|sh)$"
    DEFAULT_MATCH_DIR_RE = r"[^\.].*"
    DEFAULT_CONVENTION = conventions.reuse_v2_0

    PROJECT_CONFIG_FILE = ".mbl-licensing-checker"

    SECTION_NAME = "mbl-licensing-checker"

    def __init__(self):
        """Create a configuration parser."""
        self._cache = {}
        self._override_by_cli = None
        self._arguments = self._run_conf = None
        self._parser = self._create_argument_parser()

    # ---------------------------- Public Methods -----------------------------

    def get_default_run_configuration(self):
        """Return a `RunConfiguration` object set with default values."""
        arguments = self._parse_args([])
        return self._create_run_config(arguments)

    def parse(self):
        """Parse the configuration.

        If the convention argument was selected, overrides all
        error codes to check and disregards any error code related
        configurations from the configuration files.

        """
        self._arguments = self._parse_args()

        if not self._validate_convention(self._arguments):
            raise IllegalConfiguration()

        self._run_conf = self._create_run_config(self._arguments)

        config = self._create_check_config(self._arguments, use_defaults=False)
        self._override_by_cli = config

    @_check_initialized
    def get_user_run_configuration(self):
        """Return the run configuration for the script."""
        return self._run_conf

    @_check_initialized
    def get_files_to_check(self):
        """Generate files and error codes to check on each one.

        Walk dir trees under `self._arguments.pathnames` and yield file names
        that `match` under each directory that `match_dir`.
        The method locates the configuration for each file name and yields a
        tuple of (filename, [error_codes]).

        With every discovery of a new configuration file `IllegalConfiguration`
        might be raised.
        """
        for name in self._arguments.pathnames:
            if os.path.isdir(name):
                for dirpath, dirnames, filenames in os.walk(name):
                    config = self._get_config(os.path.abspath(dirpath))
                    match, match_dir = self._get_matches(config)

                    # Skip any subdirectories that do not match match_dir
                    dirnames[:] = [d for d in dirnames if match_dir(d)]

                    for filename in filenames:
                        if match(filename):
                            full_path = os.path.join(dirpath, filename)
                            yield (full_path, list(config.checked_codes))
            else:
                config = self._get_config(os.path.abspath(name))
                match, _ = self._get_matches(config)
                if match(name):
                    yield (name, list(config.checked_codes))

    # --------------------------- Private Methods -----------------------------

    def _get_matches(self, conf):
        """Return the `match` and `match_dir` functions for `config`."""
        match_func = re.compile(conf.match + "$").match
        match_dir_func = re.compile(conf.match_dir + "$").match
        return match_func, match_dir_func

    def _get_config_by_discovery(self, node):
        """Get a configuration for checking `node` by config discovery.

        Config discovery happens when no explicit config file is specified. The
        file system is searched for config files starting from the directory
        containing the file being checked, and up until the root directory of
        the project.

        See `_get_config` for further details.
        """
        path = self._get_node_dir(node)

        if path in self._cache:
            return self._cache[path]

        config_file = self._get_config_file_in_folder(path)

        if config_file is None:
            parent_dir, tail = os.path.split(path)
            if tail:
                # No configuration file, simply take the parent's.
                config = self._get_config(parent_dir)
            else:
                # There's no configuration file and no parent directory.
                # Use the default configuration or the one given in the CLI.
                config = self._create_check_config(self._arguments)
        else:
            # There's a config file! Read it and merge if necessary.
            options, inherit = self._read_configuration_file(config_file)

            parent_dir, tail = os.path.split(path)
            if tail and inherit:
                # There is a parent dir and we should try to merge.
                parent_config = self._get_config(parent_dir)
                config = self._merge_configuration(parent_config, options)
            else:
                # No need to merge or parent dir does not exist.
                config = self._create_check_config(options)

        return config

    def _get_config(self, node):
        """Get and cache the run configuration for `node`.

        If no configuration exists (not local and not for the parent node),
        returns and caches a default configuration.

        The algorithm:
        -------------
        * If the current directory's configuration exists in
           `self._cache` - return it.
        * If a configuration file does not exist in this directory:
          * If the directory is not a root directory:
            * Cache its configuration as this directory's and return it.
          * Else:
            * Cache a default configuration and return it.
        * Else:
          * Read the configuration file.
          * If a parent directory exists AND the configuration file
            allows inheritance:
            * Read the parent configuration by calling this function with the
              parent directory as `node`.
            * Merge the parent configuration with the current one and
              cache it.
        * If the user has specified one the convention argument in
          the CLI - return the CLI configuration with the configuration match
          clauses
        * Set the `--add-select` and `--add-ignore` CLI configurations.

        """
        if self._run_conf.config is None:
            log.debug("No config file specified, discovering.")
            config = self._get_config_by_discovery(node)
        else:
            log.debug("Using config file {}".format(self._run_conf.config))
            if not os.path.exists(self._run_conf.config):
                raise IllegalConfiguration(
                    "Configuration file {!r} specified "
                    "via --config was not found.".format(self._run_conf.config)
                )

            if None in self._cache:
                return self._cache[None]
            arguments = self._read_configuration_file(self._run_conf.config)

            if arguments is None:
                log.warning(
                    "Configuration file does not contain a "
                    "pydocstyle section. Using default configuration."
                )
                config = self._create_check_config(self._arguments)
            else:
                config = self._create_check_config(arguments)

        # Overidde configuration with passed CLI options
        final_config = {}
        for attr in CheckConfiguration._fields:
            cli_val = getattr(self._override_by_cli, attr)
            conf_val = getattr(config, attr)
            final_config[attr] = cli_val if cli_val is not None else conf_val

        config = CheckConfiguration(**final_config)

        self._set_add_arguments(config.checked_codes, self._arguments)

        # Handle caching
        if self._run_conf.config is not None:
            self._cache[None] = config
        else:
            self._cache[self._get_node_dir(node)] = config
        return config

    @staticmethod
    def _get_node_dir(node):
        """Return the absolute path of the directory of a filesystem node."""
        path = os.path.abspath(node)
        return path if os.path.isdir(path) else os.path.dirname(path)

    def _read_configuration_file(self, path):
        """Try to read and parse `path` as a configuration file.

        If the configurations were illegal (checked with
        `self._validate_convention`), raises `IllegalConfiguration`.

        Returns (arguments, should_inherit).

        """
        parser = RawConfigParser(inline_comment_prefixes=("#", ";"))
        arguments = None
        should_inherit = True

        if parser.read(path) and parser.has_section(
            ConfigurationParser.SECTION_NAME
        ):
            all_arguments = self._parser._get_optional_actions()

            argument_list = {arg.dest: arg.type for arg in all_arguments}
            # First, read the default values
            new_arguments = self._parse_args([])

            # Second, parse the configuration
            section_name = ConfigurationParser.SECTION_NAME
            for arg in parser.options(section_name):
                if arg == "inherit":
                    should_inherit = parser.getboolean(section_name, arg)
                    continue

                if arg.replace("_", "-") not in self.CONFIG_FILE_ARGUMENTS:
                    log.warning("Unknown option '{}' ignored".format(arg))
                    continue

                normalized_arg = arg.replace("-", "_")
                arg_type = argument_list[normalized_arg]
                if arg_type is int:
                    value = parser.getint(section_name, arg)
                elif arg_type == str:
                    value = parser.get(section_name, arg)
                else:
                    assert arg_type is bool
                    value = parser.getboolean(section_name, arg)
                setattr(new_arguments, normalized_arg, value)

            # Third, fix the set-arguments
            arguments = self._fix_set_arguments(new_arguments)

        if arguments is not None:
            if not self._validate_convention(arguments):
                raise IllegalConfiguration("in file: {}".format(path))

        return arguments, should_inherit

    def _merge_configuration(self, parent_config, child_arguments):
        """Merge parent config into the child options.

        The migration process requires an `options` object for the child in
        order to distinguish between mutually exclusive codes, add-select and
        add-ignore error codes.

        """
        # Copy the parent error codes so we won't override them
        error_codes = copy.deepcopy(parent_config.checked_codes)
        if child_arguments.convention is not None:
            error_codes = self._get_convention_error_codes(child_arguments)

        self._set_add_arguments(error_codes, child_arguments)

        kwargs = dict(checked_codes=error_codes)
        for key in ("match", "match_dir"):
            kwargs[key] = getattr(child_arguments, key) or getattr(
                parent_config, key
            )
        return CheckConfiguration(**kwargs)

    def _parse_args(self, args=None, values=None):
        """Parse the arguments using `self._parser` and reformat them."""
        arguments = self._parser.parse_args(args, values)
        return self._fix_set_arguments(arguments)

    @staticmethod
    def _create_run_config(arguments):
        """Create a `RunConfiguration` object from `arguments`."""
        values = {
            arg: getattr(arguments, arg) for arg in RunConfiguration._fields
        }
        return RunConfiguration(**values)

    @classmethod
    def _create_check_config(cls, arguments, use_defaults=True):
        """Create a `CheckConfiguration` object from `arguments`.

        If `use_defaults`, any of the match arguments that are `None` will
        be replaced with their default value and the default convention will be
        set for the checked codes.

        """
        checked_codes = None

        if arguments.convention is not None or use_defaults:
            checked_codes = cls._get_checked_errors(arguments)

        kwargs = dict(checked_codes=checked_codes)
        for key in ("match", "match_dir"):
            kwargs[key] = (
                getattr(cls, "DEFAULT_{}_RE".format(key.upper()))
                if getattr(arguments, key) is None and use_defaults
                else getattr(arguments, key)
            )
        return CheckConfiguration(**kwargs)

    @classmethod
    def _get_config_file_in_folder(cls, path):
        """Look for a configuration file in `path`.

        If exists return its full path, otherwise None.

        """
        if os.path.isfile(path):
            path = os.path.dirname(path)

        config = RawConfigParser()
        full_path = os.path.join(path, cls.PROJECT_CONFIG_FILE)
        if config.read(full_path) and config.has_section(cls.SECTION_NAME):
            return full_path

    @classmethod
    def _get_convention_error_codes(cls, arguments):
        """Extract the error codes from the selected convention."""
        codes = set(ErrorRegistry.get_error_codes())
        checked_codes = None

        if arguments.convention is not None:
            checked_codes = getattr(conventions, arguments.convention)

        # To not override the conventions nor the arguments - copy them.
        return copy.deepcopy(checked_codes)

    @classmethod
    def _set_add_arguments(cls, checked_codes, arguments):
        """Set `checked_codes` by the `add_ignore` or `add_select` options."""
        checked_codes |= cls._expand_error_codes(arguments.add_select)
        checked_codes -= cls._expand_error_codes(arguments.add_ignore)

    @staticmethod
    def _expand_error_codes(code_parts):
        """Return an expanded set of error codes."""
        codes = set(ErrorRegistry.get_error_codes())
        expanded_codes = set()

        try:
            for part in code_parts:
                # Dealing with split-lined configurations; The part might begin
                # with a whitespace due to the newline character.
                part = part.strip()
                if not part:
                    continue

                codes_to_add = {
                    code for code in codes if code.startswith(part)
                }
                if not codes_to_add:
                    log.warning(
                        "Error code passed is not a prefix of any "
                        "known errors: {}".format(part)
                    )
                expanded_codes.update(codes_to_add)
        except TypeError as e:
            raise IllegalConfiguration(e)

        return expanded_codes

    @classmethod
    def _get_checked_errors(cls, arguments):
        """Extract the codes needed to be checked from `arguments`."""
        checked_codes = cls._get_convention_error_codes(arguments)
        if checked_codes is None:
            checked_codes = cls.DEFAULT_CONVENTION

        cls._set_add_arguments(checked_codes, arguments)

        return checked_codes

    @classmethod
    def _validate_convention(cls, arguments):
        """Validate the convention argument if any was passed.

        Return `True` if a known convention was passed or if none was passed.
        """
        if (
            arguments.convention is not None
            and arguments.convention not in conventions
        ):
            log.error(
                "Illegal convention '{}'. Possible conventions: {}".format(
                    arguments.convention, ", ".join(conventions.keys())
                )
            )
            return False
        return True

    @classmethod
    def _fix_set_arguments(cls, arguments):
        """Alter the set arguments from None/strings to sets in place."""
        mandatory_set_arguments = ("add_ignore", "add_select")

        def _get_set(value_str):
            """Split `value_str` by the delimiter `,` and return a set.

            Removes any occurrences of '' in the set.
            Also expand error code prefixes, to avoid doing this for every
            file.

            """
            return cls._expand_error_codes(set(value_str.split(",")) - {""})

        for arg in mandatory_set_arguments:
            value = getattr(arguments, arg)
            if value is None:
                value = ""

            if not isinstance(value, Set):
                value = _get_set(value)

            setattr(arguments, arg, value)

        return arguments

    @classmethod
    def _create_argument_parser(cls):
        """Return an argument parser to parse command line arguments."""
        parser = argparse.ArgumentParser(
            description="MBL repo licensing checker application",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            usage="mbl-licensing-checker [arguments] [<file|dir>...]",
        )

        # ------------------------- Positional args ---------------------------

        parser.add_argument(
            "pathnames",
            metavar="[<file|dir>...]",
            type=str,
            nargs="*",
            default=".",
            help=(
                "List of path to file and/or directory to check for licensing."
            ),
        )

        # -------------------------- Optional args ----------------------------

        parser.add_argument("--version", action="version", version=__version__)

        # Run configuration arguments
        run_config_argument = parser.add_argument
        run_config_argument(
            "-e",
            "--explain",
            const=True,
            nargs="?",
            help="Show explanation of each error",
        )
        run_config_argument(
            "-d",
            "--debug",
            const=True,
            nargs="?",
            help="Print debug information",
        )
        run_config_argument(
            "-v",
            "--verbose",
            const=True,
            nargs="?",
            help="Print application status information",
        )
        run_config_argument(
            "--count",
            const=True,
            nargs="?",
            help="Print total number of errors to stdout",
        )
        run_config_argument(
            "--config",
            metavar="<path>",
            type=str,
            help="Search and use configuration starting from this directory",
            default=None,
        )

        # Match clauses
        run_config_argument(
            "--match",
            metavar="<pattern>",
            type=str,
            default=None,
            help=(
                "Check only files that exactly match <pattern> regular "
                "expression; default is --match='{}' which matches "
                "files that don't start with 'test_' but end with "
                "the file extensions in <pattern>"
            ).format(cls.DEFAULT_MATCH_RE),
        )
        run_config_argument(
            "--match-dir",
            metavar="<pattern>",
            type=str,
            default=None,
            help=(
                "Search only dirs that exactly match <pattern> regular "
                "expression; default is --match-dir='{}', which "
                "matches all dirs that don't start with "
                "a dot"
            ).format(cls.DEFAULT_MATCH_DIR_RE),
        )

        note_group = parser.add_argument_group(
            "Note",
            "When using --match, or --match-dir consider whether you should "
            "use a single quote (') or a double quote (\"), depending on your "
            "OS, Shell, etc.",
        )

        # Error check argument modifiers
        error_check_group = parser.add_argument_group(
            "Error Check Arguments",
            "Select the list of error codes to check for. "
            "If not specified, default to `--convention=reuse_v2_0`."
            "If you wish to change a list of error to check "
            "(for example, if you selected a known convention but wish to "
            "ignore a specific error from it or add a new one) you can "
            "use `--add-[ignore/select]` in order to do so.",
        )
        error_check_group_argument = error_check_group.add_argument
        error_check_group_argument(
            "--convention",
            metavar="<name>",
            type=str,
            default=None,
            help="Choose the basic list of checked errors by specifying "
            "an existing convention. Possible conventions: {}.".format(
                ", ".join(conventions)
            ),
        )
        error_check_group_argument(
            "--add-select",
            metavar="<codes>",
            type=str,
            default=None,
            help="Add extra error codes to check to the basic list of "
            "errors previously set --convention.",
        )
        error_check_group_argument(
            "--add-ignore",
            metavar="<codes>",
            type=str,
            default=None,
            help="Ignore extra error codes by removing them from the "
            "basic list previously set by --convention.",
        ),

        return parser


def _check_initialized(method):
    # Check that the configuration object was initialized.
    @functools.wraps(method)
    def _decorator(self, *args, **kwargs):
        if self._arguments is None:
            raise RuntimeError("using an uninitialized configuration")
        return method(self, *args, **kwargs)

    return _decorator


# Check configuration - used by the ConfigurationParser class.
CheckConfiguration = namedtuple(
    "CheckConfiguration", ("checked_codes", "match", "match_dir")
)


class IllegalConfiguration(Exception):
    """An exception for illegal configurations."""

    pass


# General configurations for mbl-licensing-checker run.
RunConfiguration = namedtuple(
    "RunConfiguration", ("explain", "debug", "verbose", "count", "config")
)
