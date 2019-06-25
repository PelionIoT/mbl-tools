#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

if [ "$1" == "-h" ]; then
    echo "Create synchonization tags on the given branches with these assumptions:"
    echo " * run in the repository checkout you want to tag;"
    echo " * the BRANCH_FROM local head is at the point to tag (i.e. the last commit synced);"
    echo " * the BRANCH_TO remote head is at the point to tag (i.e. last commit is the sync)."
    echo "Usage: $(basename "$0") [BRANCH_FROM] [BRANCH_TO]"
    exit 0
fi

REMOTE=$(git remote)

DEV=${1}
MST=${2-master}
if [ "$DEV" == "" ]; then
    # Work out default head
    HEAD=$(git remote show "$REMOTE" | grep "HEAD branch")
    DEV=${HEAD#*: }
fi

echo "BRANCH_FROM=$DEV / BRANCH_TO=$MST"

TAG_TO=${DEV}_to_${MST}
TAG_INTO=${DEV}_into_${MST}

set -x 

# Sync master with remote
git fetch "$REMOTE"
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


# Push the tags to the remote
git push "$REMOTE" "${TAG_TO}" "${TAG_INTO}"
