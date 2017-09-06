#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

## The stack of stages is abstracted out to these functions primarily to
## isolate the pain of bash arrays in conjunction with set -u.  We want
## set -u behaviour on in order to improve script robustness.  However
## bash arrays do not play nicely in this context.  Notably taking
## the ${# size of an empty array will throw an exception.

declare -a stages
stages=()

empty_stages_p ()
{
  [ -z "${stages[*]:-}" ]
}

push_stages ()
{
  stages=("$@" "${stages[@]:-}")
}

pop_stages ()
{
  item=${stages[0]}
  unset stages[0]
  stages=("${stages[@]:-}")
}

update_stage ()
{
  local action="$1"
  shift
  echo "($action) $*"
}

usage()
{
  cat <<EOF

usage: build-oe.sh [OPTION]

  --builddir DIR	Use DIR for build, default CWD.
  -h, --help		Print brief usage information and exit.
  -x			Enable shell debugging in this script.

EOF
}
args=$(getopt -o+hx -l builddir:,clean,no-clean,help,target: -n $(basename "$0") -- "$@")
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

  --clean)
    flag_clean=1
    ;;

  --no-clean)
    flag_clean=0
    ;;

  -h | --help)
    usage
    exit 0
    ;;

  --target)
    opt_prev=target
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
  builddir=$(pwd)
fi

cd "$builddir"

if empty_stages_p; then
  if [ -r "$builddir/,stage" ]; then
    # Continue from last failing stage
    stages=($(cat "$builddir/,stage"))
  else
    # Build from the start
    stages=(start)
  fi
fi

while true; do
  if empty_stages_p; then
    push_stages stop
  fi

  # Record the current build stage and shift
  echo "${stages[*]}" > "$builddir/,stage"

  pop_stages
  stage="$item"

  update_stage "$stage"
  case "$stage" in
  start)
    push_stages checkout build
    ;;

  checkout)
    url="git@github.com:ARMmbed/mbl-manifest.git"
    branch="mbl-ci"
    manifest="pinned-manifest.xml"

    rm -rf "$builddir/mbl-manifest-t"
    mkdir -p "$builddir/mbl-manifest-t"
    (cd "$builddir/mbl-manifest-t"  && repo init -u "$url" -b "$branch" -m "$manifest")
    mv "$builddir/mbl-manifest-t" "$builddir/mbl-manifest"
    push_stages sync
    ;;

  sync)
    (cd "$builddir/mbl-manifest"
     repo sync)
    ;;

  build)
    (cd "$builddir/mbl-manifest"
     set +u
     set +e
     MACHINE=raspberrypi3 DISTRO=rpb . setup-environment  "build-rpb"
     set -u
     set -e
     image="rpb-console-image"
     image="core-image-base"
     bitbake "$image"
    )
    ;;

  stop)
    printf "  completed as requested\n"
    exit 0
    ;;

  *)
    printf "error: unrecognized stage: $stage\n" 2>&1
    rm -f "$builddir/,stage"
    exit 1
    ;;
  esac
done
