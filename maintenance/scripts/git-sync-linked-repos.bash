#!/bin/bash

# TODO - can refactor this to enable more than one linked repo
# E.g. 11-2 in https://www.tldp.org/LDP/abs/html/loops1.html

# Defaults
MBL_LINKED_REPO="armmbed/mbl-core"
MBL_LINKED_FILE="armmbed/meta-mbl/meta-mbl-distro/conf/distro/mbl-linked-repositories.conf"
MBL_LINKED_LINE="SRCREV_MBL_CORE_REPO"
MANIFEST_OVERRIDE_DIR=".repo/local_manifests"
MANIFEST_OVERRIDE_FILE="mbl-linked-override.xml"
#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Create an override to match the versions of the linked repos"
    echo "$MBL_LINKED_REPO only at this time"
    echo "Usage: $(basename $0)"
    exit 0
fi

if [ ! -d ".repo" ]; then
    echo "ERROR: No .repo directory found, please run in release sync repo directory root"
    exit 1
fi

QUIET=-q
DEBUG=${DEBUG:-0}
if [ $DEBUG -ne 0 ]; then
    QUIET=
fi

# Create override file
# Currently only supports mbl-core
MBL_LINKED_SHA=$(grep "$MBL_LINKED_LINE" "$MBL_LINKED_FILE" | sed -e 's/.*\(".*"\)/\1/')
if [[ "$MBL_LINKED_SHA" =~ ^[\"0-9a-f]+$ ]]; then
    echo "Overriding $MBL_LINKED_REPO version to $MBL_LINKED_SHA"
    echo " Via $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE"
    mkdir -p "$MANIFEST_OVERRIDE_DIR"
    cat << EOF > $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remove-project name="$MBL_LINKED_REPO"/>
  <project name="$MBL_LINKED_REPO" remote="origin" revision=$MBL_LINKED_SHA/>
</manifest>
EOF
    repo sync $QUIET
else
    echo -e "\n\e[91mWARNING: Unrecognized linking SHA, not using exact $MBL_LINKED_REPO revision"
    echo -e "File:$MBL_LINKED_FILE\nSHA found:$MBL_LINKED_SHA\e[0m\n"
fi
