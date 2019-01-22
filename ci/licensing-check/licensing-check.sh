#!/bin/bash

# Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u
set -o pipefail

rc=0

find_files()
{
  # Perform the find command with the following conditions:
  # * type is a file
  # * .git directories are all ignored
  eval "find $workdir -type f -not -path \"*/\.git/*\"" | \
    while read -r file_path; do
      printf "%s " "${file_path}";
    done
}

usage()
{
  cat <<EOF

usage: licensing-check.sh [OPTION] -- [licensing-check.sh arguments]

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

# Collect all files to check
FILES_TO_CHECK=$(find_files)

printf "Run mbl-licensing-checker on files...\n"
printf "%s" "$FILES_TO_CHECK" | xargs --no-run-if-empty mbl-licensing-checker || rc=1

exit "$rc"
