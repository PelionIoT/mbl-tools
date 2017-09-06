#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u

host="github.com"

git config --global user.email "nobody@nowhere.arm.com"
git config --global user.name "nobody"
git config --global color.ui false


mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
if ! ssh-keygen -F "$host" > /dev/null; then
     ssh-keyscan -H "$host" >> ~/.ssh/known_hosts;
fi
