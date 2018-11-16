#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

execdir="$(readlink -e "$(dirname "$0")")"

default_builddir="build-mbl-manifest"
default_imagename="mbl-manifest-env"
default_containername="mbl-tools-container.$$"

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

usage: run-me.sh [OPTION] -- [build.sh arguments]

  --builddir PATH       Specify the root of the build tree.  Default ${default_builddir}.
  --downloaddir PATH    Use PATH to store downloaded packages.
  --external-manifest PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --image-name NAME     Specify the docker image name to build. Default ${default_imagename}.
  --inject-mcc PATH     Add a file to the list of mbed cloud client files
                        to be injected into a build.  This is a temporary
                        mechanism to inject development keys.
  -o, --outputdir PATH  Specify a directory to store built arifacts.
  --tty                 Enable tty creation (default).
  --no-tty              Disable tty creation.
  --workdir PATH        Specify the directory where to store artifacts.  Default ${default_builddir}.
                        Deprecated.  Use --builddir instead.
  -x                    Enable shell debugging in this script.

EOF
}

imagename="$default_imagename"
flag_tty="-t"

args=$(getopt -o+ho:x -l builddir:,downloaddir:,external-manifest:,help,image-name:,inject-mcc:,outputdir:,tty,no-tty,workdir: -n "$(basename "$0")" -- "$@")
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
  --builddir)
    opt_prev=builddir
    ;;

  --downloaddir)
    opt_prev=downloaddir
    ;;

  --external-manifest)
    opt_prev=external_manifest
    ;;

  -h | --help)
    usage
    exit 0
    ;;

  --image-name)
    opt_prev=imagename
    ;;

  --inject-mcc)
    opt_append=inject_mcc_files
    ;;

  -o | --outputdir)
    opt_prev=outputdir
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

if [ -n "${downloaddir:-}" ]; then
  downloaddir=$(readlink -f "$downloaddir")
  if [ ! -e "$downloaddir" ]; then
    printf "error: missing downloaddir %s\n" "$downloaddir" >&2
    exit 3
  fi
fi

if [ -n "${outputdir:-}" ]; then
  outputdir=$(readlink -f "$outputdir")
  if [ ! -e "$outputdir" ]; then
    printf "error: missing outputdir %s\n" "$outputdir" >&2
    exit 3
  fi
fi

if [ -n "${workdir:-}" ]; then
  printf "warning: --workdir is deprecated, use --builddir\n" >& 2
  if [ -z "${builddir:-}" ]; then
    builddir="$workdir"
  fi
fi

if [ -z "${builddir:-}" ]; then
  builddir="$default_builddir"
fi

builddir=$(readlink -f "$builddir")
mkdir -p "$builddir"

if [ -n "${inject_mcc_files:-}" ]; then
  mkdir -p "$builddir/inject-mcc"
  for file in ${inject_mcc_files:-}; do
    base="$(basename "$file")"
    cp "$file" "$builddir/inject-mcc/$base"
    build_args="${build_args:-} --inject-mcc=/work/inject-mcc/$base"
  done
fi

docker build -t "$imagename" "$execdir"

if [ -n "${external_manifest:-}" ]; then
  name="$(basename "$external_manifest")"
  cp "$external_manifest" "$builddir/$name"
  set -- "--external-manifest=/work/$name" "$@"
fi

# The ${:+} expansion of download upsets shellcheck, but we do not
# want that instance quoted because that would inject an empty
# argument when download is not defined.
# shellcheck disable=SC2086
docker run --rm -i $flag_tty \
       --name "$default_containername" \
       -e LOCAL_UID="$(id -u)" -e LOCAL_GID="$(id -g)" \
       -e SSH_AUTH_SOCK="$SSH_AUTH_SOCK" \
       ${downloaddir:+-v "$downloaddir":/downloads} \
       ${outputdir:+-v "$outputdir":/artifacts} \
       -v "$(dirname "$SSH_AUTH_SOCK"):$(dirname "$SSH_AUTH_SOCK")" \
       -v "$builddir":/work \
       "$imagename" \
       ./build.sh --builddir /work \
         ${build_args:-} \
         ${downloaddir:+--downloaddir /downloads} \
         ${outputdir:+--outputdir /artifacts} \
         "$@"
