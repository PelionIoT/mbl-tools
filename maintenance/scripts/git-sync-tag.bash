#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

REMOTE=$(git remote)

MASTER=master
# Work out default development head
HEAD=$(git remote show "$REMOTE" | grep "HEAD branch")
HEAD=${HEAD#*: }    # Remove spaces

if [ "$1" == "-h" ]; then
    echo "Create synchonization tags on the given branches with these assumptions:"
    echo " * run in the repository checkout you want to tag;"
    echo " * BRANCH_FROM local head is at point to tag (i.e. local commit synced);"
    echo " * BRANCH_TO remote head is at point to tag (i.e. remote commit is sync)."
    echo "Usage: $(basename "$0") [BRANCH_FROM] [BRANCH_TO]"
    echo "Defaults: BRANCH_FROM=$HEAD / BRANCH_TO=$MASTER"
    exit 0
fi

DEV=${1}
MST=${2-$MASTER}
if [ "$DEV" == "" ]; then
    DEV=$HEAD
fi

echo "BRANCH_FROM=$DEV / BRANCH_TO=$MST"

TAG_TO=${DEV}_to_${MST}
TAG_INTO=${DEV}_into_${MST}

set -xe

# Move to dev (but don't update - as assume this is at the right place!)
git checkout "${DEV}"

# Tagging the last synced commit from the source branch (development branch)
# Delete on the remote the previous tag
git push "$REMOTE" :"refs/tags/${TAG_TO}"

# Delete on the local the previous tag
git tag --delete "${TAG_TO}"

# Tag the <last_source_branch_synced_commit> - ASSUMPTION!
echo "Tagging ${DEV}: $(git log --format=oneline --abbrev-commit -1)"
git tag "${TAG_TO}"


# Sync master with remote
git checkout "${MST}"
git pull

# Tagging the last synced commit from the target branch (master branch)
# Delete on the remote the previous tag
git push "$REMOTE" :"refs/tags/${TAG_INTO}"

# Delete on the local the previous tag:
git tag --delete "${TAG_INTO}"

# Tag the <last_target_branch_synced_commit> - ASSUMPTION!
echo "Tagging ${MST}: $(git log --format=oneline --abbrev-commit -1)"
git tag "${TAG_INTO}"


# Push the tags to the remote
git push "$REMOTE" "${TAG_TO}" "${TAG_INTO}"
