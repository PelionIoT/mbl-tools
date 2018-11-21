#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

execdir="$(readlink -e "$(dirname "$0")")"

default_imagename="mbl-sanity-check-env"
default_containername="mbl-sanity-check-container.$$"

trap cleanup 0

cleanup() {
    # This command will return an id (eg. 43008e2a9f5a) of the running
    # container
    running_container="$(docker ps -q -f name="$default_containername")"
    if [ ! -z "$running_container" ]; then
        docker kill "$default_containername"
    fi
}

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] -- [run-me.sh arguments]

  -h, --help            Print brief usage information and exit.
  --image-name NAME     Specify the docker image name to build. Default ${default_imagename}.
  --tty                 Enable tty creation (default).
  --no-tty              Disable tty creation.
  --workdir PATH        Specify the directory to check.  Default PWD.
  -x                    Enable shell debugging in this script.

EOF
}

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

if [ -z "${workdir:-}" ]; then
  workdir="$(pwd)"
fi
workdir=$(eval readlink -f "$workdir")

docker build -t "$imagename" "$execdir"

docker run --rm -i $flag_tty \
       --name "$default_containername" \
       -e LOCAL_UID="$(id -u)" -e LOCAL_GID="$(id -g)" \
       -v "$workdir":/work "$imagename" \
       ./sanity-check.sh --workdir /work \
       "$@"
