#!/bin/bash

usage()
{
  cat <<EOF
usage: deploy-to-pypi.sh [OPTION] -- [deploy-to-pypi.sh arguments]

  -h, --help            Print brief usage information and exit.
  --workdir PATH        Specify the directory to your python wheel. Default PWD.
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
  esac
  shift 1
done

if [ -z "${workdir:-}" ]; then
  workdir="$(pwd)"
fi

DIR="$( dirname "$0" )"

docker build -t deploy-build -f "$DIR"/Dockerfile "$workdir"
docker run --name deploy-container deploy-build
docker rm deploy-container