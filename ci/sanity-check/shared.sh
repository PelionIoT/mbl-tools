#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

expand_path() {
    local path=$1
    # Using shell parameter expansion with the form ${parameter#word}
    path="${path/#\~/$HOME}"
    path=$(readlink -f "$path")
    printf "%s" "$path"
}
