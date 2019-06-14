#!/bin/bash

if [ "$1" == "-h" ]; then
    echo "Review the outstanding commits from the current branch synchonization"
    echo "Note: requires branches to have been properly tagged via git-sync-tag.bash"
    echo "Usage: $(basename $0) [BRANCH_FROM] [BRANCH_TO]"
    exit 0
fi

DEV=${1-origin/warrior-dev}
MST=${2-origin/master}

# Print out repo name and settings
echo $(basename $(git remote get-url origin) .git)
echo "BRANCH_FROM=$DEV / BRANCH_TO=$MST"

TAG_TO=$(basename $DEV)_to_$(basename $MST)


DEV_COL="\e[32m"
MST_COL="\e[33m"
NO_COL="\e[0m"

DIFF=$(git cherry -v --abbrev=7 $MST $DEV $TAG_TO)

echo -e "${MST_COL}${MST} ${DEV_COL}${DEV}${NO_COL}"

IFS=$'\n'
for line in $DIFF; do
    if [[ $line =~ ^\+ ]]; then
        echo -e "        ${DEV_COL}${line:2}${NO_COL}"
    elif [[ $line =~ ^- ]]; then
        echo -e "${MST_COL}${line:2:7}        ${line:9}${NO_COL}"
    fi
done
