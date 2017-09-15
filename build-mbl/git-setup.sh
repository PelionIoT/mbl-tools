#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

# It sets default git values, if those are not set. This avoids git complaining
# about those values missing.

if ! git config --get user.name > /dev/null; then
  git config --global user.name "nobody"
fi

if ! git config --get user.email > /dev/null; then
  git config --global user.email "nobody@nowhere.arm.com"
fi

if ! git config --get color.ui > /dev/null; then
  git config --global color.ui false
fi
