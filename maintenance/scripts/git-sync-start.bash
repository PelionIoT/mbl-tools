#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Start the release or maintenance sync process by creating a repo directory"
    echo "Usage: $(basename "$0") [--release] [--flowhelp] [WORKDIR]"
    exit 0
fi

# Should be working off master
MANIFEST=maintenance/maintenance.xml
RELEASE=0
DEVELOPMENT=0
if [ "$1" == "--release" ]; then
    # Should be working off latest dev branch
    RELEASE=1
    MANIFEST=maintenance/release.xml
    shift
elif [ "$1" == "--development" ]; then
    # Should be working off master
    DEVELOPMENT=1
    MANIFEST=maintenance/release.xml
    shift
fi

QUIET=-q
DEBUG=${DEBUG:-0}
if [ "$DEBUG" -ne 0 ]; then
    QUIET=
fi

# Currently assume we can get the manifests from the local mbl-tools checkout
# Warning! Will not pick up local modifications!
MBL_TOOLS_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MBL_TOOLS_DIR="$(cd "$MBL_TOOLS_SCRIPTS_DIR" && git rev-parse --show-toplevel)"
MBL_TOOLS_BRANCH="$(cd "$MBL_TOOLS_DIR" && git name-rev --name-only HEAD)"

if [ "$1" != "--flowhelp" ]; then
    # Create the new work directory and perform a repo sync

    WORKDIR="${1-mbl-maint}"

    if [ -d "$WORKDIR" ]; then
        echo "ERROR: work dir already exists: $WORKDIR"
        exit 1
    fi

    mkdir -p "$WORKDIR"
    cd "$WORKDIR" || exit 1

    echo "Using mbl-tools: $MBL_TOOLS_DIR @ $MBL_TOOLS_BRANCH"

    repo init $QUIET -u "$MBL_TOOLS_DIR" -b "$MBL_TOOLS_BRANCH" -m "$MANIFEST"
    repo sync $QUIET
else
    if [ ! -d ".repo" ]; then
        echo "ERROR: No .repo directory found, please run in the repo directory root"
        exit 1
    fi
fi

# Read the setting in the manifest xml we are using
REMOTE=$(grep "<remote" .repo/manifest.xml | sed -e 's|.*name=\"\(.*\)\".*|\1|')

if [ $RELEASE -eq 1 ]; then
    echo "RELEASE BRANCH flow:"
    echo "$ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-manifest.bash pinned-manifest.xml mbl-os-x.y"
    echo "$ repo start mbl-os-x.y --all"
    echo "* commit armmbed/mbl-manifest/default.xml with changes done by manifest script"
    echo "* edit/commit armmbed/mbl-tools/maintenance/release.xml to default to mbl-os-x.y"
    echo "* edit/commit armmbed/mbl-jenkins/mbl-pipeline to use mbl-os-x.y"
    echo "* edit/commit armmbed/meta-mbl/meta-mbl-distro/conf/distro/include/mbl-distro.inc to set DISTRO_VERSION"
    echo "$ repo forall -c push --set-upstream $REMOTE mbl-os-x.y"
    echo "* github: create the PRs/test and get them merged"
    echo ""
    echo "RELEASE CANDIDATE TAG flow: (assumes branched as above and built on jenkins)"
    echo "* add/commit/push armmbed/mbl-manifest/release.xml - a built pinned manifest"
    echo "$ cd armmbed/mbl-manifest; git tag mbl-os-x.y.z-rcn; git push $REMOTE mbl-os-x.y.z-rcn"
    echo ""
    echo "RELEASE TAG flow: (assumes branched and rc tag as above)"
    echo "$ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-rc-tag.bash mbl-os-x.y.z-rcn"
    echo "$ repo forall -c git tag new-release-tag"
    echo "$ repo forall -c git push $REMOTE new-release-tag"
elif [ $DEVELOPMENT -eq 1 ]; then
    echo "DEVELOPMENT BRANCH flow:"
    echo "$ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-manifest.bash armmbed/mbl-manifest/default.xml yocto-version-name-dev"
    echo "$ repo start yocto-version-name-dev --all"
    echo "* edit/commit armmbed/mbl-manifest/default.xml with changes done by manifest script."
    echo "  NOTE: Change the <default revision=\"master\" to yocto-version-name and some layers could not have the"
    echo "  yocto-version-name branch and in this case for each project add the revision=\"master\" or any specific sha."
    echo "* edit/commit armmbed/mbl-tools/maintenance/release.xml to default to yocto-version-name-dev"
    echo "* edit/commit armmbed/mbl-jenkins/mbl-pipeline to use yocto-version-name-dev"
    echo "Next you can push all the changes to github (this skips the PR flow for the changes done):"
    echo "$ repo forall -c push --set-upstream $REMOTE yocto-version-name-dev"
else
    echo "MAINTENANCE flow:"
    echo "$ repo start new-maintenance-branch --all"
    echo "* manually per project - review and pick the commits:"
    echo "  $ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-diff.bash"
    echo "  $ git cherry-pick <shas>"
    echo "  * Suggestion: keep a log of the diff output and which commits you picked"
    echo "$ repo forall -c git push --set-upstream $REMOTE new-maintenance-branch"
    echo "* github: create the PRs/test and get them merged"
    echo "  * Suggestion: create test commits for mbl-manifest/meta-mbl to point to"
    echo "  * Suggestion: new-maintenance-branch; after testing you can drop these test"
    echo "  * Suggestion: commits via rebase and push/merge without re-test"
    echo "$ repo forall -c ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-tag.bash"
fi
