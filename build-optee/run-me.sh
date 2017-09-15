#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

containername="optee"

workdir="build-optee"
workdir=$(readlink -f "$workdir")

docker build -t "$containername" ./mbl-tools/build-optee/

mkdir -p "$workdir"

docker run --rm -t -i \
       -v "$workdir":/work "$containername" \
       ./build.sh --builddir /work "$@"
