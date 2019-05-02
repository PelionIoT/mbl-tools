#!/bin/bash

WORKAREA="$1"; shift;
cd "${WORKAREA}/poky"
TEMPLATECONF=meta-pelion-os-edge/conf source oe-init-build-env
bitbake "$@"
