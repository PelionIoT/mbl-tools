#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

if [ "$1" == "-h" ]; then
    echo "Review the outstanding commits from the current branch synchonization"
    echo "Outputs the list of commits in oldest first order"
    echo "Note: requires branches to have been properly tagged via git-sync-tag.bash"
    echo "Note: must use remote (e.g. origin) in branches"
    echo "Usage: $(basename "$0") [REMOTE_BRANCH_FROM] [REMOTE_BRANCH_TO]"
    exit 0
fi

REMOTE=$(git remote)

DEV=${1}
MST=${2-$REMOTE/master}
if [ "$DEV" == "" ]; then
    # Work out default head
    HEAD=$(git remote show "$REMOTE" | grep "HEAD branch")
    DEV=$REMOTE/${HEAD#*: }
fi

# Print out repo name and settings
basename "$(git remote get-url "$REMOTE")" .git
echo "BRANCH_FROM=$DEV / BRANCH_TO=$MST"

TAG_TO=$(basename "$DEV")_to_$(basename "$MST")

DEV_COL="\e[32m"
MST_COL="\e[33m"
NO_COL="\e[0m"

DIFF=$(git cherry -v --abbrev=7 "$MST" "$DEV" "$TAG_TO")

echo -e "${MST_COL}${MST} ${DEV_COL}${DEV}${NO_COL}"

IFS=$'\n'
SHAS=""
for line in $DIFF; do
    if [[ $line =~ ^\+ ]]; then
        echo -e "        ${DEV_COL}${line:2}${NO_COL}"
        SHAS="$SHAS ${line:2:7}"
    elif [[ $line =~ ^- ]]; then
        echo -e "${MST_COL}${line:2:7}        ${line:9}${NO_COL}"
    fi
done
if [ "$SHAS" != "" ]; then
    echo "Example diff: git format-patch --stdout -1 [SHA]"
    echo "Example pick: git cherry-pick$SHAS"
fi
