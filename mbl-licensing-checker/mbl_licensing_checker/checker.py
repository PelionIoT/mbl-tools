# Based on: src/pydocstyle/checker.py
# In open-source project: https://github.com/PyCQA/pydocstyle
#
# Original file: Copyright (c) 2014-2017 Amir Rachum, <http://amir.rachum.com/>
# Modifications: Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: MIT

"""Parsed source code checkers for licensing violations."""

from . import violations
from .config import IllegalConfiguration
from .parser import Parser, StringIO
from .utils import log

__all__ = ("check",)


def check_for(is_check=True):
    def decorator(func):
        func._check_for = is_check
        return func

    return decorator


BB_FILE_EXTENSIONS = (".bb", ".bbappend", ".bbclass")


class ConventionChecker:
    """Checker for REUSE 2.0 and MBL specific license conventions.

    D10x: Missing copyright notice
    D20x: Missing licence information
    D30x: Copyright content issues
    D40x: Licence content issues
    """

    def check_source(self, source, filename):
        """Check various possible errors in a source file."""
        parser = Parser(StringIO(source))
        parser.parse_filelike()
        for this_check in self.checks:
            error = this_check(self, parser, filename)
            errors = error if hasattr(error, "__iter__") else [error]
            for error in errors:
                if error is not None:
                    partition = this_check.__doc__.partition(".\n")
                    message, _, explanation = partition
                    error.set_context(
                        filename=filename, explanation=explanation
                    )
                    yield error

    @property
    def checks(self):
        return [
            this_check
            for this_check in vars(type(self)).values()
            if hasattr(this_check, "_check_for")
        ]

    @check_for()
    def check_arm_copyright_missing(self, parser, filename):
        """D100: Missing ARM copyright notice.

        All source code written or modified by ARM should have
        an ARM copyright notice.
        """
        if parser.arm_copyright:
            if (
                parser.tpip_path
                or parser.tpip_source_uri
                or parser.tpip_copyright
            ):
                if parser.arm_copyright_tpip:
                    return
            else:
                return
        return violations.D100()

    @check_for()
    def check_tpip_path_missing(self, parser, filename):
        """D101: Missing the fully qualified path and filename.

        All files that contain Third Party Intellectual Property
        (TPIP) copied and subsequently modified must contain the
        fully qualified path and filename of the original file.
        """
        if (
            parser.arm_copyright_tpip
            or parser.tpip_source_uri
            or parser.tpip_copyright
        ):
            if not parser.tpip_path:
                return violations.D101()

    @check_for()
    def check_tpip_uri_missing(self, parser, filename):
        """D102: Missing the URI to the source code repository.

        All files that contain Third Party Intellectual Property
        (TPIP) copied and subsequently modified must contain the
        URI to the source code repository.
        """
        if (
            parser.arm_copyright_tpip
            or parser.tpip_path
            or parser.tpip_copyright
        ):
            if not parser.tpip_source_uri:
                return violations.D102()

    @check_for()
    def check_tpip_copyright_missing(self, parser, filename):
        """D103: Missing a copy of the original copyright notice.

        All files that contain Third Party Intellectual Property
        (TPIP) copied and subsequently modified must contain a
        copy of the original copyright notice
        """
        if (
            parser.tpip_source_uri
            or parser.tpip_path
            or parser.arm_copyright_tpip
        ):
            if not parser.tpip_copyright:
                return violations.D103()

    @check_for()
    def check_spdx_id_missing(self, parser, filename):
        """D200: Missing the SPDX license Identifier.

        All files must include an SPDX identifier.
        """
        if not parser.spdx_identifier:
            return violations.D200()

    @check_for()
    def check_spdx_id_not_apache_2_0(self, parser, filename):
        """D300: The SPDX license identifier should be Apache-2.0.

        `Apache-2-0` was the expected SPDX identifier.
        """
        if (
            parser.tpip_path
            or parser.tpip_source_uri
            or parser.tpip_copyright
            or parser.arm_copyright_tpip
        ):
            return
        if parser.spdx_identifier != "Apache-2-0":
            for file_extension in BB_FILE_EXTENSIONS:
                if filename.endswith(file_extension):
                    return
            return violations.D300(parser.spdx_identifier)

    @check_for()
    def check_spdx_id_not_bsd(self, parser, filename):
        """D301: The SPDX license identifier should be BSD-3-Clause.

        `BSD-3-Clause` was the expected SPDX identifier.
        """
        if (
            parser.tpip_path
            or parser.tpip_source_uri
            or parser.tpip_copyright
            or parser.arm_copyright_tpip
        ):
            return
        if parser.spdx_identifier != "BSD-3-Clause":
            for file_extension in BB_FILE_EXTENSIONS:
                if filename.endswith(file_extension):
                    return
            return violations.D301(parser.spdx_identifier)

    @check_for()
    def check_spdx_id_not_mit(self, parser, filename):
        """D302: The SPDX license identifier should be MIT.

        `MIT` was the expected SPDX identifier.
        """
        if (
            parser.tpip_path
            or parser.tpip_source_uri
            or parser.tpip_copyright
            or parser.arm_copyright_tpip
        ):
            return
        if parser.spdx_identifier != "MIT":
            for file_extension in BB_FILE_EXTENSIONS:
                if filename.endswith(file_extension):
                    return violations.D302(parser.spdx_identifier)


def check(filenames, select=None, ignore=None):
    """Generate licensing errors that exists in `filenames` iterable.

    By default, the REUSE 2.0 convention is checked. To specifically define the
    set of error codes to check for, supply either `select` or `ignore` (but
    not both). In either case, the parameter should be a collection of error
    code strings, e.g., {"D100", "D200"}.

    When supplying `select`, only specified error codes will be reported.
    When supplying `ignore`, all error codes which were not specified will be
    reported.

    Note that ignored error code refer to the entire set of possible
    error codes, which is larger than just the REUSE 2.0 convention. To your
    convenience, you may use
    `mbl_licensing_checker.violations.conventions.reuse_v2_0` as a base set to
    add or remove errors from.

    Examples
    --------
    >>> check(["foo.py"])
    <generator object check at 0x...>

    >>> check(["foo.py"], select=["D100"])
    <generator object check at 0x...>

    >>> check(["foo.py"], ignore=conventions.reuse_v2_0 - {'D100'})
    <generator object check at 0x...>

    """
    if select is not None and ignore is not None:
        raise IllegalConfiguration(
            "Cannot pass both select and ignore. "
            "They are mutually exclusive."
        )
    elif select is not None:
        checked_codes = select
    elif ignore is not None:
        checked_codes = list(
            set(violations.ErrorRegistry.get_error_codes()) - set(ignore)
        )
    else:
        checked_codes = violations.conventions.reuse_v2_0

    for filename in filenames:
        log.info("Checking file {}.".format(filename))
        try:
            with open(filename) as file:
                source = file.read()
            for error in ConventionChecker().check_source(source, filename):
                code = getattr(error, "code", None)
                if code in checked_codes:
                    yield error
        except (EnvironmentError, Exception) as error:
            log.warning("Error in file {}: {}".format(filename, error))
            yield error
