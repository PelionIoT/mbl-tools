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
printf "Running pycodestyle on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pycodestyle || rc=1

# Run pydocstyle on python files
printf "Running pydocstyle on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pydocstyle || rc=1

exit "$rc"
