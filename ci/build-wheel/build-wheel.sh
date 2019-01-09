#!/bin/bash

SCRIPT="$(realpath "$0")"
DIR="$( dirname "$SCRIPT" )"

. $DIR/../lib/parse-args.sh
. $DIR/../lib/build-py-base-image.sh

usage()
{
  cat <<EOF
usage: build-wheel.sh [OPTION] -- [build-wheel.sh arguments]

  -h, --help            Print brief usage information and exit.
  --workdir PATH        Specify the directory to check. Default PWD.
EOF
}

workdirAndHelpArgParser "$@"

buildPyBaseImage "$DIR/../lib"

docker build -t wheel-build -f "$DIR"/Dockerfile "$workdir"
docker run --name wheel-container wheel-build
docker cp wheel-container:/work/dist "$workdir"
docker rm wheel-container
