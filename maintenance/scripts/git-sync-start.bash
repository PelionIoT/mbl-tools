#!/bin/bash

#DEBUG=1

if [ "$1" == "-h" ]; then
    echo "Start the release or maintenance sync process"
    echo "Usage: $(basename $0) [--release] [WORKDIR]"
    exit 0
fi

# Should be working off master
MANIFEST=maintenance/maintenance.xml
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
MBL_TOOLS_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MBL_TOOLS_DIR="$(cd "$MBL_TOOLS_SCRIPTS_DIR" && git rev-parse --show-toplevel)"
MBL_TOOLS_BRANCH="$(cd "$MBL_TOOLS_DIR" && git name-rev --name-only HEAD)"

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
    echo "RELEASE BRANCH flow:"
    echo "$ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-manifest.bash pinned-manifest.xml mbl-os-x.y"
    echo "$ repo start new-release-branch --all"
    echo "* commit armmbed/mbl-manifest/default.xml with changes done by manifest script"
    echo "* edit/commit armmbed/mbl-tools/maintenance/release.xml to default to new-release-branch"
    echo "* edit/commit armmbed/mbl-jenkins/mbl-pipeline to use new-release-branch"
    echo "* edit/commit armmbed/meta-mbl/meta-mbl-distro/conf/distro/mbl.conf to set DISTRO_VERSION"
    echo "$ repo forall -c push --set-upstream origin new-release-branch"
    echo "* github: create the PRs/test and get them merged"
    echo ""
    echo "RELEASE CANDIDATE TAG flow: (assumes branched as above and built on jenkins)"
    echo "* add/commit/push armmbed/mbl-manifest/release.xml - a built pinned manifest"
    echo "$ cd armmbed/mbl-manifest; git tag mbl-os-x.y.z-rcn; git push origin mbl-os-x.y.z-rcn"
    echo ""
    echo "RELEASE TAG flow: (assumes branched and rc tag as above)"
    echo "$ ${MBL_TOOLS_SCRIPTS_DIR}/git-sync-rc-tag.bash mbl-os-x.y.z-rcn"
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
