#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

## UID/GID Management

# We need to manage uid/gid inside a container because the workspace
# VOLUME and the ssh agent authentication socket are shared between
# inside and outside.  We explicit capture the users uid and gid at
# 'docker run' and arrange for an entrypoint to create the necessary
# user on the fly.

# We need a username, but it doesn't matter what the name is, we only
# care that uid/gid are anchored correctly.

username="user"

# These environment variables are typically set by
# docker run -e LOCAL_UID=$(id -u) -e LOCAL_GID=$(id -g)

LOCAL_UID=${LOCAL_UID:-9001}
LOCAL_GID=${LOCAL_GID:-9001}

printf "entrypoint: starting with UID=%d GID=%d\n" "$LOCAL_UID" "$LOCAL_GID"

if groupadd -g "$LOCAL_GID" "$username"; then
   _=
else
  # We are about to test the exit code of groupadd, hence there can
  # be no statements inserted here before the if.

  # An exit code 4 indicates gid already exists, this is ok, we ignore
  # it, any other fail is a fail!
  if [ $? -ne 4 ]; then
    exit $?
  fi
fi

if useradd --shell /bin/bash -u "$LOCAL_UID" -g "$LOCAL_GID" -G sudo -c "" -m "$username"; then
  _=
else
  # We are about to test the exit code of useradd, hence there can
  # be no statements inserted here before the if.

  # An exit code 4 indicates uid already exists, this is ok, we ignore
  # it, any other fail is a fail!
  if [ $? -ne 4 ]; then
    exit $?
  fi
fi

export HOME=/home/"$username"

sed -i 's/%sudo  ALL=(ALL:ALL) ALL/%sudo ALL=(ALL:ALL) NOPASSWD:ALL/' /etc/sudoers
sudo -E -u "$username" "$@"
