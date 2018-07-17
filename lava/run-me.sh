#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

execdir="$(readlink -e "$(dirname "$0")")"
imagename="python3.7"


usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] -- [command arguments]

  -c, --cmd             Execute a command.
                        Available commands are: submit, test
  -h, --help            Print brief usage information and exit.
  -x                    Enable shell debugging in this script.

EOF
}


args=$(getopt -o+c:hx -l cmd:,help -n "$(basename "$0")" -- "$@")
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
  -c | --cmd)
    opt_prev=cmd
    ;;

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

# Let's validate $cmd
if [ -n "${cmd:-}" ]; then
  case $cmd in
    submit)
      cmd="submit-to-lava.py"
    ;;

    test)
      cmd="-m pytest"
    ;;

    *)
      printf "error: invalid option: %s\n" "$cmd" >&2
      exit 3
    ;;
  esac
else
  printf "error: missing command\n" >&2
  exit 3
fi

# Build the docker image
docker build -t "$imagename" "$execdir"

# Run the selected command
# The $cmd assignment in tht test case upsets shellcheck, but we do not
# want that instance quoted because that would inject single quotes in the
# command line
# shellcheck disable=SC2086
docker run --rm -it "$imagename" $cmd "$@"
