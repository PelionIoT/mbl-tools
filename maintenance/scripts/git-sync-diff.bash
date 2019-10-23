#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

usage()
{
    echo "Review the outstanding commits from the current branch synchonization"
    echo "Outputs the list of commits in oldest first order"
    echo "Note: requires branches to have been properly tagged via git-sync-tag.bash"
    echo "Note: must use remote (e.g. origin) in branches"
    echo "Note: use --no-tag to review more commits, in case of bad maintenance tags"
    echo "Note: use --no-date to not show dates of the commits"
    echo "Usage: $(basename "$0") [--no-tag] [--no-date] [REMOTE_BRANCH_FROM] [REMOTE_BRANCH_TO]"
    exit 0
}

NO_TAG=0
COMMIT_DATE=1
while [ $# -gt 0 ]; do
    case $1 in
    --no-tag)
        NO_TAG=1
        ;;
    --no-date)
        COMMIT_DATE=0
        ;;
    --help|-h)
        usage
        ;;
    *)
        break
        ;;
    esac
    shift
done


REMOTE=$(git remote)

DEV=${1}
MST=${2-$REMOTE/master}
if [ "$DEV" == "" ]; then
    # Work out default head
    HEAD=$(git remote show "$REMOTE" | grep "HEAD branch")
    DEV=$REMOTE/${HEAD#*: }
fi

# Print out repo name and settings
echo "REPO: $(basename "$(git remote get-url "$REMOTE")" .git)"
echo "BRANCH_FROM=$DEV / BRANCH_TO=$MST"

TAG_TO=$(basename "$DEV")_to_$(basename "$MST")

DATE_COL="\e[36m"
WARN_COL="\e[31m"
DEV_COL="\e[32m"
MST_COL="\e[33m"
NO_COL="\e[0m"

if [ $NO_TAG -eq 1 ]; then
    echo "INFO: NOT stopping at tag $TAG_TO"
    DIFF=$(git cherry -v --abbrev=7 "$MST" "$DEV")
else
    # Get the diff using the tag, but double-check it seems good!
    ALL_COMMITS=$(git cherry -v --abbrev=7 "$MST" "$DEV" | awk '$0 ~ "^+" {count++} END {print count}')
    DIFF=$(git cherry -v --abbrev=7 "$MST" "$DEV" "$TAG_TO")
    TAG_COMMITS=$(printf "%s" "$DIFF" | awk '$0 ~ "^+" {count++} END {print count}')
    if [ "$ALL_COMMITS" != "$TAG_COMMITS" ]; then
        echo -e "${WARN_COL}!!!WARNING!!! Tag $TAG_TO maybe incorrect"
        echo -e "  Tag commits ($TAG_COMMITS) does not match all commits ($ALL_COMMITS)"
        echo -e "  Please review using --no-tag option${NO_COL}"
    fi
fi

if [ $COMMIT_DATE -eq 1 ]; then
    CDATE="${DATE_COL}date "
else
    CDATE=""
fi

echo -e "${CDATE}${MST_COL}${MST} ${DEV_COL}${DEV}${NO_COL}"

IFS=$'\n'
SHAS=""
for line in $DIFF; do
    if [ $COMMIT_DATE -eq 1 ]; then
        CDATE=$(git log -1 --format="%ci" "${line:2:7}")
        CDATE="${DATE_COL}${CDATE%% *} "
    fi
    if [[ $line =~ ^\+ ]]; then
        echo -e "${CDATE}        ${DEV_COL}${line:2}${NO_COL}"
        SHAS="$SHAS ${line:2:7}"
    elif [[ $line =~ ^- ]]; then
        echo -e "${CDATE}${MST_COL}${line:2:7}        ${line:9}${NO_COL}"
    fi
done
if [ "$SHAS" != "" ]; then
    echo "Example diff: git format-patch --stdout -1 [SHA]"
    echo "Example pick: git cherry-pick$SHAS"
fi
