#!/bin/bash

# Copyright (c) 2018 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"
rc=0

find_files_with_mime()
{
  local mime="$1"
  find "$workdir" -type f | \
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
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty black -v --check --diff || rc=1

# Run pycodestyle on python files
printf "Running pycodestyle on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pycodestyle || rc=1

# Run pep257 on python files
printf "Running pep257 on python files...\n"
printf "%s" "$PYTHON_FILES" | xargs --no-run-if-empty pep257 || rc=1

exit "$rc"
