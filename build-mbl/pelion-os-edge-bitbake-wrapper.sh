#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

WORKAREA="$1"; shift;
cd "${WORKAREA}/poky"
TEMPLATECONF=meta-pelion-os-edge/conf source oe-init-build-env
bitbake "$@"
