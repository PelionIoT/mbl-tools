#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# Defaults
MANIFEST_OVERRIDE_DIR=".repo/local_manifests"
MANIFEST_OVERRIDE_FILE="mbl-rctags-override.xml"
MBL_MANIFEST_REPO="armmbed/mbl-manifest"
MBL_MANIFEST_FILE="$MBL_MANIFEST_REPO/release.xml"

#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Switch to the given release candidate via override; and"
    echo "Create an override to repo sync to pinned versions of arm repos"
    echo "Usage: $(basename "$0") MBL_RC_TAG"
    echo "  MBL_RC_TAG - the release candidate tag of mbl-manifest"
    exit 0
fi

if [ ! -d ".repo" ]; then
    echo "ERROR: No .repo directory found, please run in release sync repo directory root"
    exit 1
fi

MBL_RC_TAG=$1
if [ "$MBL_RC_TAG" == "" ]; then
    echo "ERROR: Missing release candidate tag"
    exit 2
fi

DEBUG=${DEBUG:-0}
QUIET=-q
if [ "$DEBUG" -ne 0 ]; then
    QUIET=
fi

MBL_TOOLS_SCRIPTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Create override for this RC tag
echo "Overriding $MBL_MANIFEST_REPO version to $MBL_RC_TAG"
echo " Via $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE"
mkdir -p "$MANIFEST_OVERRIDE_DIR"

cat << EOF > $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remove-project name="$MBL_MANIFEST_REPO"/>
  <project name="$MBL_MANIFEST_REPO" remote="origin" revision="refs/tags/$MBL_RC_TAG"/>
</manifest>
EOF
repo sync $QUIET

# Perform the MBL manifest read and override and sync using this newly checked out
# mbl-manifest repo (without changing the mbl-manifest default.xml file)
"$MBL_TOOLS_SCRIPTS_DIR"/git-sync-manifest.bash --tag-only "$MBL_MANIFEST_FILE"
