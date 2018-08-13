#!/usr/bin/env python3

# Copyright (c) 2018 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

"""Check tabs existence on shell scripts."""

import argparse
import sys


def check_tabs(path):
    """Check tabs existence for given path.

    Count the number of tabs found on a given path

    :param: path of the file to analyse
    :return: number of errors

    """
    error_count = 0

    with open(path) as fd:
        lineno = 0
        for line in fd:
            lineno += 1

            if "\t" in line:
                sys.stderr.write(
                    "{}:{}: error: TAB character instead of "
                    "SPACEs.\n".format(path, lineno)
                )
                error_count += 1

    return error_count


def main(args):
    """Main execution."""
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", nargs="*")
    args = parser.parse_args(args)

    error_count = 0
    for path in args.FILE:
        error_count += check_tabs(path)

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
