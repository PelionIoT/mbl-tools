#!/bin/bash

# Defaults
MANIFEST_OVERRIDE_DIR=".repo/local_manifests"
MANIFEST_OVERRIDE_FILE="mbl-manifest-override.xml"
MANIFEST_ARM_REPO=".*(armmbed/[a-z\-]+).*"
MANIFEST_PROJECT=".*<project name=\"([\/a-zA-Z0-9_\-]+).*revision=\"([a-f0-9]+).*"
MBL_MANIFEST_FILE="armmbed/mbl-manifest/default.xml"

#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Create a new pinned manifest of non-arm repos using supplied pins; and"
    echo "Update to use pinned versions of arm repos"
    echo "Usage: $(basename $0) PINNED_MANIFEST.xml"
    exit 0
fi

if [ ! -d ".repo" ]; then
    echo "ERROR: No .repo directory found, please run in release sync repo directory root"
    exit 1
fi

MANIFEST=$1
if [ "$MANIFEST" == "" -o  ! -f "$MANIFEST" ]; then
    echo "ERROR: Invalid manifest file - $MANIFEST"
    exit 1
fi

DEBUG=${DEBUG:-0}
QUIET=-q
if [ $DEBUG -ne 0 ]; then
    QUIET=
fi

OVERRIDE_STR=""
OVERRIDE_REPOS=""
VALID=0
# Run through the pinned manifest for 2 reasons:
# 1. Work out the pinned versions of the armmbed repos we should be branching
# 2. Create a pinned version of the non-arm repos in mbl-manifest default.xml
while IFS= read -r line
do
    if [ $VALID -eq 0 ]; then
        if [ "$line" == "<manifest>" ]; then
            VALID=1
        fi
    else
        if [[ "$line" =~ $MANIFEST_ARM_REPO ]]; then
            # Found an Arm project that needs overriding to match the pinned version
            OVERRIDE_REPOS="${BASH_REMATCH[1]} $OVERRIDE_REPOS"

            # Fix project lines that are missing the correct ending - replace "> with "\> 
            line=${line/\"\>/\"\/\>}
            # Default to existing origin remotes rather than github
            line=${line/\"github\"/\"origin\"}
            # Remove any paths from the project
            line=$(echo $line | sed -e 's/path=\"[a-z/-]*\"//')
            OVERRIDE_STR="$OVERRIDE_STR  <remove-project name=\"${BASH_REMATCH[1]}\"/>\n  $line\n"
        elif [[ "$line" =~ $MANIFEST_PROJECT ]]; then
            repo=${BASH_REMATCH[1]}
            echo "Pinning $repo at ${BASH_REMATCH[2]}"
            sed -i "s|.*${repo}.*|$line|" $MBL_MANIFEST_FILE
        else
            if [ $DEBUG -eq 1 ]; then echo "IGNORED:$line"; fi
        fi
    fi
done < "$MANIFEST"

if [ "$OVERRIDE_REPOS" != "" ]; then
    echo "Overriding Arm repo versions for $OVERRIDE_REPOS"
    echo "Via $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE"
    mkdir -p "$MANIFEST_OVERRIDE_DIR"
    echo -e "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<manifest>" > $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE
    echo -e "$OVERRIDE_STR</manifest>" >> $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE
fi

if [ $VALID -ne 1 ]; then
    echo "ERROR: Invalid manifest file - $MANIFEST"
fi
