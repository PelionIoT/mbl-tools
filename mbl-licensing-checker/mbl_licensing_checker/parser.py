# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-2-Clause
"""Source code parser."""

import re
from io import StringIO

from .utils import find_pattern


ARM_COPYRIGHT_PATTERN = re.compile(
    r"""
    ^
    (.*)
    \b Copyright \s+
    \(c\) \s+
    \d\d\d\d(\s*-\s*\d\d\d\d)? ,? \s+
    Arm \s+ Limited \s+ and \s+ Contributors. \s+
    All \s+ rights
    ($|\b)
    """,
    re.X,
)

TPIP_PATH_PATTERN = re.compile(
    r"""
    ^
    (.*)
    \b Based \s on: \s+
    .+
    $
    """,
    re.X,
)

TPIP_URI_PATTERN = re.compile(
    r"""
    ^
    (.*)
    \b In \s open-source \s project: \s+
    .+
    $
    """,
    re.X,
)

TPIP_COPYRIGHT_PATTERN = re.compile(
    r"""
    ^
    (.*)
    \b Original \s file: \s+
    .+
    $
    """,
    re.X,
)

LICENSE_INFORMATION = re.compile(
    r"""
    ^
    (.*)
    \b SPDX-License-Identifier: \s+
    .+
    $
    """,
    re.X,
)


class Parser:
    """Parse the given file-like object."""

    def __init__(self, filelike):
        """Create a source code parser."""
        self.source = filelike.readlines()
        self.arm_copyright = None
        self.arm_copyright_tpip = None
        self.tpip_path = None
        self.tpip_source_uri = None
        self.tpip_copyright = None
        self.spdx_identifier = None

    # ---------------------------- Public Methods -----------------------------

    def parse_filelike(self):
        """Parse the source code."""
        self._check_arm_copyright()

        self._check_tpip_path()

        self._check_tpip_source_uri()

        self._check_tpip_copyright()

        self._check_spdx_identifier()

    # --------------------------- Private Methods -----------------------------

    def _check_arm_copyright(self):
        """Check if the file contains an ARM copyright.

        Also check if the copyright is included in a TPIP.
        """
        match_group = find_pattern(self.source, ARM_COPYRIGHT_PATTERN)

        if match_group:
            self.arm_copyright = match_group(0)

            if match_group(1) and "Modifications:" in match_group(1):
                self.arm_copyright_tpip = match_group(1)
            else:
                self.arm_copyright_tpip = None

    def _check_tpip_path(self):
        """Check if the file contains the path fo the original file."""
        match_group = find_pattern(self.source, TPIP_PATH_PATTERN)
        self.tpip_path = None if not match_group else match_group(0)

    def _check_tpip_source_uri(self):
        """Check if the file contains the URI to the original file."""
        match_group = find_pattern(self.source, TPIP_URI_PATTERN)
        self.tpip_source_uri = None if not match_group else match_group(0)

    def _check_tpip_copyright(self):
        """Check if the file include the original copyright."""
        match_group = find_pattern(self.source, TPIP_COPYRIGHT_PATTERN)
        self.tpip_copyright = None if not match_group else match_group(0)

    def _check_spdx_identifier(self):
        """Check if the file contains an SPDX id.

        The id must in a line that match expect the pattern
        LICENSE_INFORMATION.
        """
        match_group = find_pattern(self.source, LICENSE_INFORMATION)
        self.spdx_identifier = (
            None
            if not match_group
            else match_group(0).replace(" ", "").split(":")[1]
        )
