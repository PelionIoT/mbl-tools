#!/bin/bash

# Copyright (c) 2020 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u
set -o pipefail

rc=0

usage()
{
  cat <<EOF

usage: clang-tidy-check.sh [OPTION] -- [clang-tidy-check.sh arguments]

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

echo "Building project with clang-tidy checks enabled.\n"
cmake "$workdir" "-DCMAKE_CXX_CLANG_TIDY=clang-tidy;-checks=*,-clang-analyzer-cplusplus*,clang-analyzer-*" \
    -DCMAKE_CXX_COMPILER=clang \
    -DCMAKE_INSTALL_LIBDIR=/usr/lib \
    -DCMAKE_INSTALL_BINDIR=/usr/bin \
    -B/tmp/ || rc=1

make -C /tmp || rc=1

exit $rc
