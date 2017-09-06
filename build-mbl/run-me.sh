#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

containername="mbl-manifest-env"

workdir="build-mbl-manifest"
workdir=$(readlink -f "$workdir")

docker build -t "$containername" ./mbl-tools/build-mbl/

mkdir -p "$workdir"

docker run --rm -t -i -v $(dirname $SSH_AUTH_SOCK):$(dirname $SSH_AUTH_SOCK) -e SSH_AUTH_SOCK=$SSH_AUTH_SOCK -v "$workdir":/work "$containername" ./build.sh --builddir /work "$@"
