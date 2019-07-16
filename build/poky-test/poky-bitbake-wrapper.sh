#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

WORKAREA="$1"; shift;
cd "${WORKAREA}/layers/poky"

COMMAND="$*"; shift

set +u
set +e
# shellcheck disable=SC1091
TEMPLATECONF=meta-poky/conf source oe-init-build-env

set -e
set -u

$COMMAND
