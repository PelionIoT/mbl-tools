#!/usr/bin/env python

import argparse
import sys


def check(path):
    error_count = 0

    with open(path) as fd:
        lineno = 0
        for line in fd:
            lineno += 1

            if "\t" in line:
                sys.stderr.write("%s:%d: error: TAB character instead of "
                                 "SPACEs.\n" % (path, lineno))
                error_count += 1

    return error_count


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", nargs="*")
    args = parser.parse_args(args)

    error_count = 0
    for path in args.FILE:
        error_count += check(path)

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
