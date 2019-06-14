#!/bin/bash

# Defaults
MBL_LINKED_REPO="armmbed/mbl-core"
MBL_LINKED_FILE="armmbed/meta-mbl/meta-mbl-distro/conf/distro/mbl-linked-repositories.conf"
MBL_LINKED_LINE="SRCREV_MBL_CORE_REPO"
MANIFEST_OVERRIDE_DIR=".repo/local_manifests"
MANIFEST_OVERRIDE_FILE="mbl-core-override.xml"
#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Start the release or maintenance sync process"
    echo "Usage: $(basename $0) [--release] [WORKDIR]"
    exit 0
fi

# Should be working off master
MANIFEST=maintenance/default.xml
RELEASE=0
if [ "$1" == "--release" ]; then
    # Should be working off latest dev branch
    RELEASE=1
    MANIFEST=maintenance/release.xml
    shift
fi

QUIET=-q
DEBUG=${DEBUG:-0}
if [ $DEBUG -ne 0 ]; then
    QUIET=
fi

# Currently assume we can get the manifests from the local mbl-tools checkout
# Warning! Will not pick up local modifications!
MBL_TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel)"
MBL_TOOLS_BRANCH="$(cd $MBL_TOOLS_DIR && git name-rev --name-only HEAD)"
MBL_TOOLS_SCRIPTS_DIR="${MBL_TOOLS_DIR}/maintenance/scripts"

WORKDIR="${1-mbl-maint}"

if [ -d "$WORKDIR" ]; then
    echo "ERROR: work dir already exists: $WORKDIR"
    exit 1
fi

mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "Using mbl-tools: $MBL_TOOLS_DIR @ $MBL_TOOLS_BRANCH"

repo init $QUIET -u "$MBL_TOOLS_DIR" -b "$MBL_TOOLS_BRANCH" -m "$MANIFEST"
repo sync $QUIET

if [ $RELEASE -eq 1 ]; then
    # Create override file
    # Currently only supports mbl-core
    MBL_LINKED_SHA=$(grep "$MBL_LINKED_LINE" "$MBL_LINKED_FILE" | sed -e 's/.*\(".*"\)/\1/')
    if [[ "$MBL_LINKED_SHA" =~ ^[\"0-9a-f]+$ ]]; then
        echo "Overriding $MBL_LINKED_REPO version to $MBL_LINKED_SHA"
        echo "Via $MANIFEST_OVERRIDE_DIR/$MANIFEST_OVERRIDE_FILE"
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

    echo "RELEASE BRANCH flow:"
    echo "$ repo start new-release-branch --all"
    echo "* edit/commit mbl-tools/maintenance/release.xml to default to new-release-branch"
    echo "* edit/commit mbl-jenkins/mbl-pipeline to use new-release-branch"
    echo "* edit/commit meta-mbl/meta-mbl-distro/conf/distro/mbl.conf to set DISTRO_VERSION"
    echo "$ repo forall -c push --set-upstream origin new-release-branch"
    echo "* github: create the PRs/test and get them merged"
    echo ""
    echo "RELEASE TAG flow: (assumes release.xml is pointing to release branches)"
    echo "$ repo forall -c git tag new-release-tag"
    echo "$ repo forall -c git push origin new-release-tag"
else
    echo "MAINTENANCE flow:"
    echo "$ repo start new-maintenance-branch --all"
    echo "* manually per project - review and pick the commits:"
    echo "  $ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-diff.bash [dev-branch-name]"
    echo "  $ git cherry-pick <shas>"
    echo "$ repo forall -c git push --set-upstream origin new-maintenance-branch"
    echo "* github: create the PRs/test and get them merged"
    echo "$ repo forall -c ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-tag.bash [dev-branch-name]"
fi
