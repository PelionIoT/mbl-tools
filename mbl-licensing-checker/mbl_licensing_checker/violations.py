# Based on: src/pydocstyle/violations.py
# In open-source project: https://github.com/PyCQA/pydocstyle
#
# Original file: Copyright (c) 2014-2017 Amir Rachum, <http://amir.rachum.com/>
# Modifications: Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: MIT
"""License violation definition."""

from itertools import dropwhile
from functools import partial
from collections import namedtuple
from typing import Iterable, Optional, List, Callable, Any

from .utils import is_blank


__all__ = ("Error", "ErrorRegistry", "conventions")


ErrorParams = namedtuple("ErrorParams", ["code", "short_desc", "context"])


class Error:
    """Error in docstring style."""

    # Options that define how errors are printed:
    explain = False

    def __init__(
        self,
        code: str,
        short_desc: str,
        context: str,
        *parameters: Iterable[str]
    ) -> None:
        """Initialize the object.

        `parameters` are specific to the created error.
        """
        self.code = code
        self.short_desc = short_desc
        self.context = context
        self.parameters = parameters
        self.src_code = None  # type: Optional[str]
        self.filename = None  # type: Optional[str]
        self.explanation = None  # type: Optional[str]

    def set_context(self, filename: str, explanation: str) -> None:
        """Set the source code context for this error."""
        self.filename = filename
        self.explanation = explanation

    @property
    def message(self) -> str:
        """Return the message to print to the user."""
        ret = "{}: {}".format(self.code, self.short_desc)
        if self.context is not None:
            specific_error_msg = self.context.format(*self.parameters)
            ret += " ({})".format(specific_error_msg)
        return ret

    def __str__(self) -> str:
        """Set the informal string representation of an instance."""
        if self.explanation:
            self.explanation = "\n".join(
                l for l in self.explanation.split("\n") if not is_blank(l)
            )
        template = "{filename}: \n        {message}"
        if self.explain:
            template += "\n\n{explanation}\n\n"
        return template.format(
            **{
                name: getattr(self, name)
                for name in ["filename", "message", "explanation"]
            }
        )

    def __repr__(self) -> str:
        """Set the official string representation of an instance."""
        return str(self)

    def __lt__(self, other: "Error") -> bool:
        """Override the less than operator for an instance based on filename.
        """
        return self.filename < other.filename


class ErrorRegistry:
    """A registry of all error codes, divided to groups."""

    groups = []  # type: ignore

    class ErrorGroup:
        """A group of similarly themed errors."""

        def __init__(self, prefix: str, name: str) -> None:
            """Initialize the object.

            `Prefix` should be the common prefix for errors in this group,
            e.g., "D1".
            `name` is the name of the group (its subject).

            """
            self.prefix = prefix
            self.name = name
            self.errors = []  # type: List[ErrorParams]

        def create_error(
            self,
            error_code: str,
            error_desc: str,
            error_context: Optional[str] = None,
        ) -> Callable[[Iterable[str]], Error]:
            """Create an error, register it to this group and return it."""
            error_params = ErrorParams(error_code, error_desc, error_context)
            factory = partial(Error, *error_params)
            self.errors.append(error_params)
            return factory

    @classmethod
    def create_group(cls, prefix: str, name: str) -> ErrorGroup:
        """Create a new error group and return it."""
        group = cls.ErrorGroup(prefix, name)
        cls.groups.append(group)
        return group

    @classmethod
    def get_error_codes(cls) -> Iterable[str]:
        """Yield all registered codes."""
        for group in cls.groups:
            for error in group.errors:
                yield error.code

    @classmethod
    def to_rst(cls) -> str:
        """Output the registry as reStructuredText, for documentation."""
        sep_line = "+" + 6 * "-" + "+" + "-" * 71 + "+\n"
        blank_line = "|" + 78 * " " + "|\n"
        table = ""
        for group in cls.groups:
            table += sep_line
            table += blank_line
            table += "|" + "**{}**".format(group.name).center(78) + "|\n"
            table += blank_line
            for error in group.errors:
                table += sep_line
                table += (
                    "|"
                    + error.code.center(6)
                    + "| "
                    + error.short_desc.ljust(70)
                    + "|\n"
                )
        table += sep_line
        return table


D1xx = ErrorRegistry.create_group("D1", "Missing copyright notice")
D100 = D1xx.create_error("D100", "Missing ARM copyright notice")
D101 = D1xx.create_error(
    "D101", "Missing the fully qualified path and filename"
)
D102 = D1xx.create_error(
    "D102", "Missing the URI to the source code repository"
)
D103 = D1xx.create_error(
    "D103", "Missing a copy of the original copyright notice"
)
D2xx = ErrorRegistry.create_group("D2", "Missing licence information")
D200 = D2xx.create_error("D200", "Missing the SPDX license Identifier")
D3xx = ErrorRegistry.create_group("D3", "License Information issues")
D300 = D3xx.create_error(
    "D300", "The SPDX license identifier should be Apache-2.0", "not {0}"
)
D301 = D3xx.create_error(
    "D301", "The SPDX license identifier should be BSD-3-Clause", "not {0}"
)
D302 = D3xx.create_error(
    "D302", "The SPDX license identifier should be MIT", "not {0}"
)


class AttrDict(dict):
    def __getattr__(self, item: str) -> Any:
        return self[item]


all_errors = set(ErrorRegistry.get_error_codes())


conventions = AttrDict({"reuse_v2_0": all_errors - {"D300"}, "none": set()})
