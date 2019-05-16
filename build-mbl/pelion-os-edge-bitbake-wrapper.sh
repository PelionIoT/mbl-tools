#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

WORKAREA="$1"; shift;
cd "${WORKAREA}/poky"

set +u
set +e
# shellcheck disable=SC1091
TEMPLATECONF=meta-pelion-edge/conf source oe-init-build-env
set -e
set -u

bitbake "$@"
