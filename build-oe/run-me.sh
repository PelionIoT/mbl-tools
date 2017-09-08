#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

containername="oe"

workdir="build-oe"
workdir=$(readlink -f "$workdir")

docker build -t "$containername" ./mbl-tools/build-oe/

mkdir -p "$workdir"

docker run --rm -t -i \
       -v "$workdir":/work "$containername" \
       ./build.sh --builddir /work "$@"
