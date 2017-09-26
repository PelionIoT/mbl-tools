#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"

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

usage: build.sh [OPTION] [STAGE]..

  --builddir DIR        Use DIR for build, default CWD.
  -h, --help            Print brief usage information and exit.
  -x                    Enable shell debugging in this script.

  STAGE                 Start execution at STAGE, default previous
                        exit stage or start.

Useful STAGE names:
  start                 Start at the beginning.

EOF
}
args=$(getopt -o+hx -l builddir:,clean,no-clean,help,target: -n "$(basename "$0")" -- "$@")
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

if [ $# -gt 0 ]; then
  stages=("$@")
fi

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
    "$execdir/git-setup.sh"
    "$execdir/ssh-setup.sh"

    mkdir -p "$builddir"
    if [ ! -d poky ]; then
        (cd "$builddir"
         pwd
         git clone git://git.yoctoproject.org/poky
         cd "$builddir/poky"
         git checkout pyro)
    fi
    ;;

  rebase)
    (cd "$builddir/poky"
     git fetch -a
     git rebase origin/pyro)
    ;;

  build)
    (cd "$builddir/poky"
     set +e
     set +u
     source oe-init-build-env
     set -e
     set -u

     bitbake core-image-base)
    ;;

  stop)
    printf "  completed as requested\n"
    exit 0
    ;;

  *)
    printf "error: unrecognized stage: %s\n" "$stage" 2>&1
    rm -f "$builddir/,stage"
    exit 1
    ;;
  esac
done
