#!/bin/bash

SCRIPT="$(realpath "$0")"
DIR="$( dirname "$SCRIPT" )"

. $DIR/../lib/parse-args.sh
. $DIR/../lib/build-py-base-image.sh

usage()
{
  cat <<EOF
usage: deploy-to-pypi.sh [OPTION] -- [deploy-to-pypi.sh arguments]

  -h, --help            Print brief usage information and exit.
  --workdir PATH        Specify the directory to your python wheel. Default PWD.
EOF
}

workdirAndHelpArgParser "$@"

buildPyBaseImage "$DIR/../lib"

docker build -t deploy-build -f "$DIR"/Dockerfile "$workdir"
docker run --name deploy-container deploy-build
docker rm deploy-container