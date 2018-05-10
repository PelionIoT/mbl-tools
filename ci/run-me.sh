#!/bin/bash

# Copyright (c) 2018 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"

write_info()
{
  printf "info:"
  # We explicit want the info() function to take a format string followed by arguments, hence:
  # shellcheck disable=SC2059
  printf "$@"
}

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
  write_info "(%s) %s\n" "$action" "$*"
}

rm_atomic ()
{
  local path="$1"

  # Ensure we cleanup after an interrupted previous deletion attempt
  rm -rf "$path.rm"

  # Atomic rename of the tree to delete.
  if [ -e "$path" ]; then
    mv -f "$path" "$path.rm"

    # Non atomic delete of the renamed tree.
    rm -rf "$path.rm"
  fi
}

default_builddir="$execdir/mbl-ci"
default_manifest_branch="master"
default_manifest_name="default.xml"

trap cleanup 0

cleanup() {
    echo
}

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] [STAGE]..

  --builddir=PATH        Specify the root of the build tree. Default ${default_builddir}.
  -h, --help             Print brief usage information and exit.
  --manifest-branch=NAME Specify manifest branch name. Default ${default_manifest_branch}.
  --manifest-name=NAME   Specify the manifest to use. Default ${default_manifest_name}.
  --topic-branch=NAME    Specify the topic branch to build.
  -x                     Enable shell debugging in this script.

  STAGE                  Start execution at STAGE, default previous
                         exit stage or start.

Useful STAGE names:
  clean                  Blow away the working tree and start over.
  start                  Start at the beginning.

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

if [ $# -gt 0 ]; then
  stages=("$@")
fi

if [ -z "${builddir:-}" ]; then
  builddir="$(pwd)"
else
  mkdir -p "$builddir"
  builddir="$(readlink -f "$builddir")"
fi

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
  clean)
    rm_atomic "$builddir"
    push_stages start
    ;;

  start)
    push_stages stop
    ;;

  stop)
    write_info "completed as requested\n"
    exit 0
    ;;

  *)
    printf "error: unrecognized stage: %s\n" "$stage" 2>&1
    rm -f "$builddir/,stage"
    exit 1
    ;;
  esac
done
