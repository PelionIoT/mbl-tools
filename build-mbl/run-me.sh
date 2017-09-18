#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] -- [build.sh arguments]

  -h, --help            Print brief usage information and exit.
  -x                    Enable shell debugging in this script.

EOF
}

args=$(getopt -o+hx -l help -n "$(basename "$0")" -- "$@")
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

containername="mbl-manifest-env"

workdir="build-mbl-manifest"
workdir=$(readlink -f "$workdir")

docker build -t "$containername" ./mbl-tools/build-mbl/

mkdir -p "$workdir"

docker run --rm -t -i \
       -e LOCAL_UID="$(id -u)" -e LOCAL_GID="$(id -g)" \
       -e SSH_AUTH_SOCK="$SSH_AUTH_SOCK" \
       -v "$(dirname "$SSH_AUTH_SOCK"):$(dirname "$SSH_AUTH_SOCK")" \
       -v "$workdir":/work "$containername" \
       ./build.sh --builddir /work "$@"
