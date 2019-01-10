# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Source code parser."""

import re
from io import StringIO


ARM_COPYRIGHT_PATTERN = re.compile(
    r"""
    ^
    (.*)
    \b Copyright \s+
    \(c\) \s+
    \d\d\d\d(\s*-\s*\d\d\d\d)? \s+
    Arm \s+ Limited \s+ and \s+ Contributors. \s+
    All \s+ rights \s+ reserved. \s*
    $
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
        self.license_identifier = None
        self.spdx_identifier = None

    # ---------------------------- Public Methods -----------------------------

    def parse_filelike(self):
        """Parse the source code."""
        self._check_arm_copyright()
        self._check_tpip_path()
        self._check_tpip_source_uri()
        self._check_tpip_copyright()
        self._check_license_information()
        self._check_spdx_identifier()

    # --------------------------- Private Methods -----------------------------

    def _check_arm_copyright(self):
        """Check if the file contains an ARM copyright.
        
        Also check if the copyright is included in a TPIP.
        """
        self.arm_copyright = None
        self.arm_copyright_tpip = None

        for line in self.source:
            match = ARM_COPYRIGHT_PATTERN.search(line)
            if match:
                self.arm_copyright = match.group(0)
                if match.group(1):
                    if "Modifications:" in match.group(1):
                        self.arm_copyright_tpip = match.group(1)
                        break
                break

    def _check_tpip_path(self):
        """Check if the file contains the qualified path fo the original file."""
        self.tpip_path = None

        for line in self.source:
            match = TPIP_PATH_PATTERN.search(line)
            if match:
                self.tpip_path = match.group(0)
                break

    def _check_tpip_source_uri(self):
        """Check if the file contains the URI to the original file."""
        self.tpip_source_uri = None

        for line in self.source:
            match = TPIP_URI_PATTERN.search(line)
            if match:
                self.tpip_source_uri = match.group(0)
                break

    def _check_tpip_copyright(self):
        """Check if the file include the original copyright."""
        self.tpip_copyright = None

        for line in self.source:
            match = TPIP_COPYRIGHT_PATTERN.search(line)
            if match:
                self.tpip_copyright = match.group(0)
                break

    def _check_license_information(self):
        """Check if the file includes a license identifier."""
        self.license_identifier = None

        for line in self.source:
            match = LICENSE_INFORMATION.search(line)
            if match:
                self.license_identifier = match.group(0)
                break

    def _check_spdx_identifier(self):
        """Check the spdx identifier if one is provided."""
        self.spdx_identifier = None

        for line in self.source:
            match = LICENSE_INFORMATION.search(line)
            if match:
                self.spdx_identifier = self.license_identifier.replace(
                    " ", ""
                ).split(":")[1]
