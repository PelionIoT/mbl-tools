#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

# It sets known_hosts with the right key of github.com. In this way git doesn't
# complain about the host not being recognised when cloning repositories from
# github via ssh

host="github.com"

mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
if ! ssh-keygen -F "$host" > /dev/null; then
     ssh-keyscan -H "$host" >> ~/.ssh/known_hosts
fi
