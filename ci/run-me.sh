#!/bin/bash

# Copyright (c) 2018 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

execdir="$(readlink -e "$(dirname "$0")")"

default_builddir=$execdir
default_manifest_branch="master"
default_manifest_name="default.xml"

trap cleanup 0

cleanup() {
    echo
}

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION]

  --builddir=PATH        Specify the root of the build tree. Default ${default_builddir}.
  -h, --help             Print brief usage information and exit.
  --manifest-branch=NAME Specify manifest branch name. Default ${default_manifest_branch}.
  --manifest-name=NAME   Specify the manifest to use. Default ${default_manifest_name}.
  --topic-branch=NAME    Specify the topic branch to build.
  -x                     Enable shell debugging in this script.

EOF
}

args=$(getopt -o+hx -l builddir:,help,manifest-branch:,manifest-name:,topic-branch: -n "$(basename "$0")" -- "$@")
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

  -h | --help)
    usage
    exit 0
    ;;

  --manifest-branch)
    opt_prev=manifest_branch
    ;;

  --manifest-name)
    opt_prev=manifest_name
    ;;

  --topic-branch)
    opt_prev=topic_branch
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


if [ -z "${builddir:-}" ]; then
  builddir="$default_builddir"
fi

builddir=$(readlink -f "$builddir")
mkdir -p "$builddir"

if [ -z "${manifest_branch:-}" ]; then
  manifest_branch="$default_manifest_branch"
fi

if [ -z "${manifest_name:-}" ]; then
  manifest_name="$default_manifest_name"
fi

if [ -z "${topic_branch:-}" ]; then
  printf "error: topic branch not specified" >&2
  exit 3
fi

echo "$manifest_branch" "$manifest_name" "$topic_branch"
