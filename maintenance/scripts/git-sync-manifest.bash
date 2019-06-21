#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# Defaults
MANIFEST_OVERRIDE_DIR=".repo/local_manifests"
MANIFEST_OVERRIDE_FILE="mbl-manifest-override.xml"
MANIFEST_ARM_REPO=".*(armmbed/[a-z\-]+).*"
MANIFEST_PROJECT=".*<project name=\"([\/a-zA-Z0-9_\-]+).*revision=\"([a-f0-9]+).*"
MBL_MANIFEST_FILE="armmbed/mbl-manifest/default.xml"

#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Create a new manifest of pinned non-arm repos using supplied pins; and"
    echo "Set the arm repos to use the supplied MBL_BRANCH; and"
    echo "Create an override to repo sync to pinned versions of arm repos"
    echo "Usage: $(basename "$0") PINNED_MANIFEST.xml MBL_BRANCH"
    echo "  PINNED_MANIFEST.xml - the pinned manifest from the last good build"
    echo "  MBL_BRANCH - the name of the new branch (for release)"
    exit 0
fi

if [ ! -d ".repo" ]; then
    echo "ERROR: No .repo directory found, please run in release sync repo directory root"
    exit 1
fi

TAG_ONLY=0
if [ "$1" == "--tag-only" ]; then
    # Mode used by the git-sync-rc-tag.bash script to just use the release.xml to set
    # up the overrides for the arm repos, don't mess with the default.xml manifest
    TAG_ONLY=1
    shift
fi

MANIFEST=$1
if [ "$MANIFEST" == "" ] || [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Invalid manifest file name - $MANIFEST"
    exit 2
fi

MBL_BRANCH=$2
if [ $TAG_ONLY -eq 0 ] && [ "$MBL_BRANCH" == "" ]; then
    echo "ERROR: Missing branch name"
    exit 2
fi

DEBUG=${DEBUG:-0}
QUIET=-q
if [ "$DEBUG" -ne 0 ]; then
    QUIET=
fi

MBL_TOOLS_SCRIPTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

OVERRIDE_STR=""
OVERRIDE_REPOS=""
VALID=0
# Run through the pinned manifest for 2 reasons:
# 1. Work out the pinned versions of the armmbed repos we should be branching
# 2. Create a pinned version of the non-arm repos in mbl-manifest default.xml
if [ $TAG_ONLY -eq 0 ]; then echo "Updating $MBL_MANIFEST_FILE"; fi
while IFS= read -r line
do
    if [ $VALID -eq 0 ]; then
        if [ "$line" == "<manifest>" ]; then
            VALID=1
        fi
    else
        if [[ "$line" =~ $MANIFEST_ARM_REPO ]]; then
            # Found an Arm project that needs overriding to match the pinned version
            repo="${BASH_REMATCH[1]}"
            OVERRIDE_REPOS="$repo $OVERRIDE_REPOS"

            # Set up the override details for this repo
            # Fix project lines that are missing the correct ending - replace "> with "\> 
            line=${line/\"\>/\"\/\>}
            # Default to existing origin remotes rather than github
            line=${line/\"github\"/\"origin\"}
            # Remove any paths from the project
            line=$(echo "$line" | sed -e 's/path=\"[a-z/-]*\"//')
            OVERRIDE_STR="$OVERRIDE_STR  <remove-project name=\"$repo\"/>\n  $line\n"

            if [ $TAG_ONLY -eq 0 ]; then
                # Update the arm repo to use the branch - altering the existing MBL manifest
                echo " Setting branch $MBL_BRANCH for $repo"
                sed -i "s|\(.*${repo}.*revision=\"\).*\(\".*\)|\1$MBL_BRANCH\2|" $MBL_MANIFEST_FILE
            fi
        elif [[ $TAG_ONLY -eq 0 && "$line" =~ $MANIFEST_PROJECT ]]; then
            # Pin the non-arm repo - altering the existing MBL manifest
            repo="${BASH_REMATCH[1]}"
            echo " Pinning $repo at ${BASH_REMATCH[2]}"
            sed -i "s|.*${repo}.*|$line|" $MBL_MANIFEST_FILE
        else
            if [ "$DEBUG" -eq 1 ]; then echo "IGNORED:$line"; fi
            if [[ "$line" =~ revision=\"master\" ]]; then
                echo -e "\n\e[91mWARNING: Using pinned manifest file that references the \"master\" version\e[0m\n"
            fi
        fi
    fi
done < "$MANIFEST"

if [ "$VALID" -ne 1 ]; then
    echo "ERROR: Invalid manifest file contents - $MANIFEST"
    exit 1
fi

# Just an blank line for formatting reasons
if [ "$TAG_ONLY" -eq 0 ]; then echo ""; fi

if [ "$OVERRIDE_REPOS" != "" ]; then
    echo "Overriding versions for $OVERRIDE_REPOS"
    echo " Via $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE"
    mkdir -p "$MANIFEST_OVERRIDE_DIR"
    echo -e "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<manifest>" > $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE
    echo -e "$OVERRIDE_STR</manifest>" >> $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE

    # Re-sync using overrides
    repo sync $QUIET
fi

# Now override the linked repos (even if we haven't overridden anything above)
"$MBL_TOOLS_SCRIPTS_DIR"/git-sync-linked-repos.bash
