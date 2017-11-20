#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

# Workspace layout:
# --buildir ROOT
#
# ROOT/
#  download
#  machine-<MACHINE>/
#    ,stage
#    mbl-manifest

set -e
set -u
set -o pipefail

execdir="$(readlink -e "$(dirname "$0")")"

write_info()
{
  printf "info:"
  # We explicit want the info() function to take a format string followed by arguments, hence:
  # shellcheck disable=SC2059
  printf "$@"
}

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
  write_info "(%s) %s\n" "$action" "$*"
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

all_machines="imx7s-warp raspberrypi3"

default_branch="master"
default_manifest="default.xml"
default_url="git@github.com:ARMmbed/mbl-manifest.git"
default_machines="raspberrypi3"
default_distro="mbl"
default_images="mbl-console-image mbl-console-image-test"

# Test if a machine name appears in the all_machines list.
#

valid_machine_p()
{
  local candidate="$1"
  local machine

  for machine in $all_machines; do
    if [ "$candidate" == "$machine" ]; then
      return 0
    fi
  done

  return 1
}

maybe_compress()
{
    local path="$1"

    rm -f "$path.gz"
    if [ "$flag_compress" -eq 1 ]; then
        write_info "compress artifact %s\n" "$(basename "$path")"
        gzip "$path"
    fi
}

usage()
{
  cat <<EOF

usage: build.sh [OPTION] [STAGE]..

  -j, --jobs NUMBER     Set the number of parallel processes. Default # CPU on the host.
  --branch BRANCH       Name the branch to checkout. Default ${default_branch}.
  --[no-]compress       Enable image artifact compression, default enabled.
  --builddir DIR        Use DIR for build, default CWD.
  --downloaddir DIR     Use DIR to store downloaded packages. Default \$builddir/download
  --external-manifest=PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --image IMAGE         Select an alternative image.  Default $default_images.
                        This option can be repeated to add multiple images.
  --inject-mcc PATH     Add a file to the list of mbed cloud client files
                        to be injected into a build.  This is a temporary
                        mechanism to inject development keys.
  --machine=MACHINE     Add a machine to build.  Default ${default_machines}.
  --manifest=MANIFEST   Name the manifest file. Default ${default_manifest}.
  -o, --outputdir PATH  Directory to output build artifacts.
  --url=URL             Name the URL to clone. Default ${default_url}.
  -x                    Enable shell debugging in this script.

  STAGE                 Start execution at STAGE, default previous
                        exit stage or start.

Useful STAGE names:
  clean                 Blow away the working tree and start over.
  start                 Start at the beginning.
  build                 Execute the bitbake build for all images and machines.

EOF
}

branch="$default_branch"
url="$default_url"
distro="$default_distro"
flag_compress=1

args=$(getopt -o+hj:o:x -l branch:,builddir:,compress,no-compress,downloaddir:,external-manifest:,help,image:,inject-mcc:,jobs:,machine:,manifest:,outputdir:,url: -n "$(basename "$0")" -- "$@")
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

  --compress)
    flag_compress=1
    ;;
  
  --no-compress)
    flag_compress=0
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

  --image)
    opt_append=images
    ;;

  --inject-mcc)
    opt_append=inject_mcc_files
    ;;

  -j | --jobs)
    opt_prev=flag_jobs
    ;;

  --machine)
    opt_append=machines
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

if [ -n "${external_manifest:-}" -a -n "${manifest:-}" ]; then
    printf "error: --external-manifest and --manifest are mutually exclusive.\n" >&2
    exit 3
fi

if [ -z "${manifest:-}" ]; then
  manifest="$default_manifest"
fi

if [ $# -gt 0 ]; then
  stages=("$@")
fi

if [ -z "${builddir:-}" ]; then
  builddir="$(pwd)"
else
  mkdir -p "$builddir"
  builddir="$(readlink -f "$builddir")"
fi

if [ -z "${images:-}" ]; then
  images="$default_images"
fi

if [ -z "${machines:-}" ]; then
  machines="$default_machines"
fi

for machine in $machines; do
  if ! valid_machine_p "$machine"; then
    printf "error: unrecognized machine '%s'\n" "$machine" >&2
    exit 3
  fi
done

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
    # We checkout one copy of mbl-manifest specifically for the
    # purpose of pinning the manifest. Once we have a pinned manifest
    # we checkout one further version of mbl-manifest per machine we
    # want to build.  The per machine mbl-manifest is forced to the
    # pinned manifest.
    if [ ! -e "$builddir/mbl-manifest" ]; then
      repo_init_atomic "$builddir/mbl-manifest" -u "$url" -b "$branch" -m "$manifest"
    fi
    push_stages sync
    ;;

  sync)
    if [ -n "${external_manifest:-}" ]; then
        name="$(basename "$external_manifest")"
        manifest="custom-$name"
        cp "$external_manifest" "$builddir/mbl-manifest/.repo/manifests/$manifest"
    fi
    (cd "$builddir/mbl-manifest"; repo init -b "$branch" -m "$manifest")
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

    push_stages checkout-pinned
    ;;

  checkout-pinned)
    # We now have a pinned manifest, we checkout an instance of
    # mbl-manifest for each machine we want to build. This per machine
    # mbl-manifest is forced to the pinned manifest generated above.
    # Since we are going to force the use of the pinned manifest, it
    # does not matter what branch or manifest we ask repo for here, we
    # just accept repo's defaults.
    for machine in $machines; do
      if [ ! -e "$builddir/machine-$machine/mbl-manifest" ]; then
        mkdir -p "$builddir/machine-$machine"
        # Default branch and manifest, we will override the manifest anyway.
        repo_init_atomic "$builddir/machine-$machine/mbl-manifest" -u "$url"
      fi
    done
    push_stages sync-pinned
    ;;

  sync-pinned)
    for machine in $machines; do
      cp "$builddir/pinned-manifest.xml" "$builddir/machine-$machine/mbl-manifest/.repo/manifests/"
      (cd "$builddir/machine-$machine/mbl-manifest"
       repo init -m "pinned-manifest.xml"
       repo sync
      )
    done
    push_stages setup
    ;;

  setup)
    for machine in $machines; do
      (cd "$builddir/machine-$machine/mbl-manifest"
       set +u
       set +e
       MACHINE="$machine" DISTRO="$distro" . setup-environment "build-mbl"
       set -u
       set -e
      )
    done
    push_stages inject
    ;;

  inject)
    if [ -n "${inject_mcc_files:-}" ]; then
      for machine in $machines; do
        for file in $inject_mcc_files; do
          base="$(basename "$file")"
          cp "$file" "$builddir/machine-$machine/mbl-manifest/build-mbl/$base"
        done
      done
    fi
    push_stages build
    ;;

  build)
    for machine in $machines; do
      (cd "$builddir/machine-$machine/mbl-manifest"
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

       # images is a space separated list of options, it should not be
       # quoted because it will form multiple options rather than one
       # option. However ideally each option in the list should be
       # quoted.
       # shellcheck disable=SC2086
       bitbake $images
      )
    done
    push_stages artifact
    ;;

  artifact)
    if [ -n "${outputdir:-}" ]; then
      for machine in $machines; do
        bbtmpdir="$builddir/machine-$machine/mbl-manifest/build-mbl/tmp-$distro-glibc"
        machinedir="$outputdir/machine/$machine"
        for image in $images; do
          imagedir="$machinedir/images/$image"

          # We are interested in the image...
          mkdir -p "$imagedir/images"

          case $machine in
          imx7s-warp)
            suffixes="manifest tar.xz wic.gz"
            ;;
          raspberrypi3)
            suffixes="rpi-sdimg"
            ;;
          esac
            
          for suffix in $suffixes
          do
            write_info "save artifact %s\n" "$image-$machine.$suffix"
            cp "$bbtmpdir/deploy/images/$machine/$image-$machine.$suffix" "$imagedir/images"
            case $suffix in
            rpi-sdimg)
              maybe_compress "$imagedir/images/$image-$machine.$suffix"
              ;;
            esac
          done

          # Dot graphs
          mkdir -p "$imagedir/dot/"
          bh_path="$builddir/machine-$machine/mbl-manifest/build-mbl/buildhistory/images/${machine/-/_}/glibc/$image"
          for path in "$bh_path/"*.dot; do
            if [ -e "$path" ]; then          
              write_info "save artifact %s\n" "$(basename "$path")"
              cp "$path" "$imagedir/dot/"
            fi
          done

          # Build information
          mkdir -p "$imagedir/info/"
          for path in "$bh_path/"*.txt; do
            if [ -e "$path" ]; then          
              write_info "save artifact %s\n" "$(basename "$path")"
              cp "$path" "$imagedir/info/"
            fi
          done
        done

        # ... the license information...
        write_info "save artifact licenses\n"
        tar c -C "$bbtmpdir/deploy" -f "$machinedir/licenses.tar" "licenses"

        maybe_compress "$machinedir/licenses.tar"
      done
    fi
    ;;

  stop)
    write_info "completed as requested\n"
    exit 0
    ;;

  *)
    printf "error: unrecognized stage: %s\n" "$stage" 2>&1
    rm -f "$builddir/,stage"
    exit 1
    ;;
  esac
done
