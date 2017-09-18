#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

default_workdir="build-mbl-manifest"
default_imagename="mbl-manifest-env"

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] -- [build.sh arguments]

  -h, --help            Print brief usage information and exit.
  --image-name NAME     Specify the docker image name to build. Default ${default_imagename}.
  --tty                 Enable tty creation (default).
  --no-tty              Disable tty creation.
  --workdir PATH        Specify the directory where to store artifacts. Default ${default_workdir}.
  -x                    Enable shell debugging in this script.

EOF
}

workdir="$default_workdir"
imagename="$default_imagename"
flag_tty="-t"

args=$(getopt -o+hx -l help,image-name:,tty,no-tty,workdir: -n "$(basename "$0")" -- "$@")
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

  --image-name)
    opt_prev=imagename
    ;;

  --tty)
    flag_tty="-t"
    ;;

  --no-tty)
    flag_tty=
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

workdir=$(readlink -f "$workdir")
mkdir -p "$workdir"

dockerfiledir="$(readlink -e "$(dirname "$0")")"
docker build -t "$imagename" "$dockerfiledir"

docker run --rm -i $flag_tty \
       -e LOCAL_UID="$(id -u)" -e LOCAL_GID="$(id -g)" \
       -e SSH_AUTH_SOCK="$SSH_AUTH_SOCK" \
       -v "$(dirname "$SSH_AUTH_SOCK"):$(dirname "$SSH_AUTH_SOCK")" \
       -v "$workdir":/work "$imagename" \
       ./build.sh --builddir /work "$@"
