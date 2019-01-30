#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"
rc=0

find_files_with_mime()
{
  local mime="$1"
  local nosanitycheck_dirs=""

  # If a directory contains .nosanitycheck, the whole subtree will be ignored
  # This is done in two steps:
  # * build a list find all directories to be ignored
  # * pass this list to find command

  # Find all directories to be ignored and stores the result in a find option
  # format. This is done finding .nosanitycheck files and getting the full path
  # of the containing directory (using dirname)
  # NOTE: process substitution has to be used in order to redirect stdout to a
  # variable which needs to exist in the current process.
  while read -r dir_path; do
    nosanitycheck_dirs+=" -o \( -path ${dir_path} -prune \)"
  done < <(find "$workdir" -name .nosanitycheck -printf "%h\n")

  # Performs the find command with the following conditions:
  # * type is a file
  # * .git directories are all ignored
  # * directories containing .nosanitycheck are skipped
  # NOTE: eval is needed here because it doesn't escape \( \) when it expands
  # $nosanitycheck_dirs variable
  eval "find $workdir -type f -not -path \"*/\.git/*\" $nosanitycheck_dirs" | \
    while read -r file_path; do
      if file -i "${file_path}" | grep -q "$mime";
        then printf "%s " "${file_path}";
      fi;
    done
}

usage()
{
  cat <<EOF

usage: sanity-check.sh [OPTION] -- [sanity-check.sh arguments]

  -h, --help            Print brief usage information and exit.
  --workdir PATH        Specify the directory to check. Default PWD.
  -x                    Enable shell debugging in this script.

EOF
}

args=$(getopt -o+hx -l help,workdir: -n "$(basename "$0")" -- "$@")
eval set -- "$args"
while [ $# -gt 0 ]; do
  if [ -n "${opt_prev:-}" ]; then
    eval "$opt_prev=\$1"
    opt_prev=
    shift 1
    continue
  elif [ -n "${opt_append:-}" ]; then
    eval "$opt_append=\"\${$opt_append:-} \$1\""
    opt_append=
    shift 1
    continue
  fi
  case $1 in
  -h | --help)
    usage
    exit 0
    ;;

  --workdir)
    opt_prev=workdir
    ;;

  -x)
    set -x
    ;;

  --)
    shift
    break 2
    ;;
  esac
  shift 1
done

if [ -z "${workdir:-}" ]; then
  workdir="$(pwd)"
fi

workdir=$(readlink -f "$workdir")

# Collect all shell files
SHELL_FILES=$(find_files_with_mime "text/x-shellscript")

# Custom script to check tabs existence in shell scripts
printf "Running tab_finder.py on shell files...\n"
printf "%s" "$SHELL_FILES" | xargs --no-run-if-empty "$execdir/tab_finder.py" || rc=1

# Run shellcheck on shell files
printf "Running shellcheck on shell files...\n"
printf "%s" "$SHELL_FILES" | xargs --no-run-if-empty shellcheck --format=gcc  || rc=1

# Collect all Python files
PYTHON_FILES=$(find_files_with_mime "text/x-python")

# Run black on python files - https://black.readthedocs.io/en/stable/
printf "Running black on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty black --line-length 79 -v --check --diff || rc=1

# Run pycodestyle on python files
# --ignore override the default ignore list hence we need to explicitly specify
# the default list of errors that pycodestyle would ignore by default.
# More info: https://github.com/PyCQA/pycodestyle/blob/master/docs/intro.rst#error-codes
PYCODESTYLE_DEFAULT_IGNORE="E121,E123,E126,E133,E226,E241,E242,E704,W503,W504,W505"
# Ignore E203 errors though - they can be spurious
# (https://github.com/PyCQA/pycodestyle/issues/373)
PYCODESTYLE_MBL_IGNORE="E203"
PYCODESTYLE_IGNORE="$PYCODESTYLE_DEFAULT_IGNORE,$PYCODESTYLE_MBL_IGNORE"
printf "Running pycodestyle on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pycodestyle --ignore="$PYCODESTYLE_IGNORE" || rc=1

# Run pydocstyle on python files
# When pydocstyle is given a directory to check it will, by default, skip
# "test_" files. We're passing pydocstyle full paths to each file though, and
# the directory part of the paths prevent "test_" files matching pydocstyle's
# filter. Adjust it here so that "test_" files are actually skipped.
printf "Running pydocstyle on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pydocstyle --match='(?!.*test_).*\.py' || rc=1

exit "$rc"
