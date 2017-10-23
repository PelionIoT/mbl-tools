#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"

## The stack of stages is abstracted out to these functions primarily to
## isolate the pain of bash arrays in conjunction with set -u.  We want
## set -u behaviour on in order to improve script robustness.  However
## bash arrays do not play nicely in this context.  Notably taking
## the ${# size of an empty array will throw an exception.

declare -a stages
stages=()

empty_stages_p ()
{
  [ -z "${stages[*]:-}" ]
}

push_stages ()
{
  stages=("$@" "${stages[@]:-}")
}

pop_stages ()
{
  item=${stages[0]}
  unset stages[0]
  stages=("${stages[@]:-}")
}

update_stage ()
{
  local action="$1"
  shift
  echo "($action) $*"
}

rm_atomic ()
{
  local path="$1"

  # Ensure we cleanup after an interrupted previous deletion attempt
  rm -rf "$path.rm"

  # Atomic rename of the tree to delete.
  if [ -e "$path" ]; then
    mv -f "$path" "$path.rm"

    # Non atomic delete of the renamed tree.
    rm -rf "$path.rm"
  fi
}

repo_init_atomic ()
{
  local path="$1"
  shift

  # Ensure we remove any previous interrupted init
  rm -rf "$path-ri"

  mkdir -p "$path-ri"
  (cd "$path-ri" && repo init "$@")
  mv "$path-ri" "$path"
}

default_branch="master"
default_manifest="default.xml"
default_url="git@github.com:ARMmbed/mbl-manifest.git"
default_machine="raspberrypi3"
default_distro="mbl"
default_image="mbl-console-image"

usage()
{
  cat <<EOF

usage: build.sh [OPTION] [STAGE]..

  -j, --jobs NUMBER     Set the number of parallel processes. Default # CPU on the host.
  --branch BRANCH       Name the branch to checkout. Default ${default_branch}.
  --builddir DIR        Use DIR for build, default CWD.
  --downloaddir DIR     Use DIR to store downloaded packages. Default \$builddir/download
  --external-manifest=PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --manifest=MANIFEST   Name the manifest file. Default ${default_manifest}.
  -o, --outputdir PATH  Directory to output build artifacts.
  --url=URL             Name the URL to clone. Default ${default_url}.
  -x                    Enable shell debugging in this script.

  STAGE                 Start execution at STAGE, default previous
                        exit stage or start.

Useful STAGE names:
  clean                 Blow away the working tree and start over.
  start                 Start at the beginning.

EOF
}

branch="$default_branch"
manifest="$default_manifest"
url="$default_url"
machine="$default_machine"
distro="$default_distro"
image="$default_image"

args=$(getopt -o+hj:o:x -l branch:,builddir:,downloaddir:,external-manifest:,help,jobs:,manifest:,outputdir:,url: -n "$(basename "$0")" -- "$@")
eval set -- "$args"
while [ $# -gt 0 ]; do
  if [ -n "${opt_prev:-}" ]; then
    eval "$opt_prev=\$1"
    opt_prev=
    shift 1
    continue
  elif [ -n "${opt_append:-}" ]; then
    eval "$opt_append=\"\${$opt_append:-} \$1\""
    opt_append=
    shift 1
    continue
  fi
  case $1 in
  --branch)
    opt_prev=branch
    ;;

  --builddir)
    opt_prev=builddir
    ;;

  --downloaddir)
    opt_prev=downloaddir
    ;;

  --external-manifest)
    opt_prev=external_manifest
    ;;

  -h | --help)
    usage
    exit 0
    ;;

  -j | --jobs)
    opt_prev=flag_jobs
    ;;

  --manifest)
    opt_prev=manifest
    ;;

  -o | --outputdir)
    opt_prev=outputdir
    ;;

  --url)
    opt_prev=url
    ;;

  -x)
    set -x
    ;;

  --)
    shift
    break 2
    ;;
  esac
  shift 1
done

if [ $# -gt 0 ]; then
  stages=("$@")
fi

if [ -z "${builddir:-}" ]; then
  builddir="$(pwd)"
else
  mkdir -p "$builddir"
  builddir="$(readlink -f "$builddir")"
fi

if [ -n "${outputdir:-}" ]; then
  outputdir="$(readlink -f "$outputdir")"
fi

if empty_stages_p; then
  if [ -r "$builddir/,stage" ]; then
    # Continue from last failing stage
    stages=($(cat "$builddir/,stage"))
  else
    # Build from the start
    stages=(start)
  fi
fi

"$execdir/git-setup.sh"
"$execdir/ssh-setup.sh"

while true; do
  if empty_stages_p; then
    push_stages stop
  fi

  # Record the current build stage and shift
  echo "${stages[*]}" > "$builddir/,stage"

  pop_stages
  stage="$item"

  update_stage "$stage"
  case "$stage" in
  clean)
    rm_atomic "$builddir/mbl-manifest"
    push_stages start
    ;;

  start)
    push_stages checkout
    ;;

  checkout)
    rm_atomic "$builddir/mbl-manifest"
    repo_init_atomic "$builddir/mbl-manifest" -u "$url" -b "$branch" -m "$manifest"
    push_stages sync
    ;;

  sync)
    if [ -n "${external_manifest:-}" ]; then
        name="$(basename "$external_manifest")"
        manifest="custom-$name"
        cp "$external_manifest" "$builddir/mbl-manifest/.repo/manifests/$manifest"
    fi
    (cd "$builddir/mbl-manifest"; repo init -m "$manifest")
    (cd "$builddir/mbl-manifest"; repo sync)
    
    push_stages pin
    ;;

  pin)
    (cd "$builddir/mbl-manifest"
     repo manifest -r -o "$builddir/pinned-manifest.xml"
    )

    # If we are saving build artifacts, then save them as they are
    # created rather than waiting for the end of the build process,
    # this makes debug of build issues easier.
    if [ -n "${outputdir:-}" ]; then
      cp "$builddir/pinned-manifest.xml" "$outputdir/pinned-manifest.xml"
    fi

    push_stages switch-to-pinned
    ;;

  switch-to-pinned)
    (cd "$builddir/mbl-manifest"
     cp "$builddir/pinned-manifest.xml" "$builddir/mbl-manifest/.repo/manifests/"
     repo init -m "pinned-manifest.xml"
     repo sync
    )
    push_stages build
    ;;

  build)
    (cd "$builddir/mbl-manifest"
     set +u
     set +e
     MACHINE="$machine" DISTRO="$distro" . setup-environment "build-mbl"
     set -u
     set -e

     # This needs to be done after the setup otherwise bitbake does not have
     # visibility of these variables
     if [ -n "${flag_jobs:-}" ]; then
       export PARALLEL_MAKE="-j $flag_jobs"
       export BB_NUMBER_THREADS="$flag_jobs"
       export BB_ENV_EXTRAWHITE="$BB_ENV_EXTRAWHITE PARALLEL_MAKE BB_NUMBER_THREADS"
     fi

     if [ -n "${downloaddir:-}" ]; then
       downloaddir=$(readlink -f "$downloaddir")
       export DL_DIR="$downloaddir"
       export BB_ENV_EXTRAWHITE="$BB_ENV_EXTRAWHITE DL_DIR"
     fi

     bitbake "$image"
    )
    push_stages artifact
    ;;

  artifact)
    if [ -n "${outputdir:-}" ]; then
      bbtmpdir="$builddir/mbl-manifest/build-mbl/tmp-$distro-glibc"

      # We are interested in the image...
      cp "$bbtmpdir/deploy/images/$machine/$image-$machine.rpi-sdimg" "$outputdir"

      # ... the license information...
      cp -r "$bbtmpdir/deploy/licenses/" "$outputdir"
    fi
    ;;

  stop)
    printf "  completed as requested\n"
    exit 0
    ;;

  *)
    printf "error: unrecognized stage: %s\n" "$stage" 2>&1
    rm -f "$builddir/,stage"
    exit 1
    ;;
  esac
done
