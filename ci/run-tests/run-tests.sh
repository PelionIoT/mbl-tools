#!/bin/bash

SCRIPT="$(realpath "$0")"
DIR="$( dirname "$SCRIPT" )"

. $DIR/../lib/parse-args.sh
. $DIR/../lib/build-py-base-image.sh

usage()
{
  cat <<EOF
usage: run-tests.sh [OPTION] -- [run-tests.sh arguments]

  -h, --help            Print brief usage information and exit.
  --workdir PATH        Specify the directory to your python package repo. Default PWD.
EOF
}

workdirAndHelpArgParser "$@"

buildPyBaseImage "$DIR/../lib"

docker build -t test-build -f "$DIR"/Dockerfile "$workdir"
docker run --name test-container test-build
docker cp test-container:work/report "$workdir"
docker rm test-container
