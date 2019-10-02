#!/bin/bash

# Copyright (c) 2018-2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

# It sets known_hosts with the right keys for git cloud repositories.
# In this way git doesn't complain about the host not being recognised when
# cloning repositories via ssh.

# Default cloud repos list (separated by spaces).
# Other examples: ssh.dev.azure.com gitlab.com bitbucket.org git.code.sf.net
# Note: We don't add these by default as it takes time to add the keys, and we
# can't assume access.
hosts="github.com"

# List of extra hosts supplied on the command line, via the --repo-host
# argument in build.sh
extra_hosts="$*"

mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
for host in $hosts $extra_hosts; do
    if ! ssh-keygen -F "$host" > /dev/null; then
        ssh-keyscan -H "$host" >> ~/.ssh/known_hosts
    fi
done
