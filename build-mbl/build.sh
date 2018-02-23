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

all_machines="imx7s-warp-mbl raspberrypi3"

default_branch="master"
default_manifest="default.xml"
default_url="git@github.com:ARMmbed/mbl-manifest.git"
default_machines="raspberrypi3"
default_distro="mbl"
default_images="mbl-console-image mbl-console-image-test"

# Set of license package name (PN) and package version name (PVN) exceptions
# This hash array uses a key (PN or PVN) created from reading the recipeinfo
# Then the key is replaced with value found in this array so that the bitbake
# environment display command will find the right package
declare -A license_package_exceptions
license_package_exceptions=(
  ["binutils-cross-arm"]="binutils-cross"
  ["docker"]="docker/docker"
  ["gcc-cross-arm_7.3.0"]="gcc-cross_7.3")

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

define_conf()
{
  local path="$1"
  local k="$2"
  local v="$3"

  rm -f "$path.new"
  grep -v "$k" "$path" > "$path.new"
  printf "%s = \"%s\"\n" "$k" "$v" >> "$path.new"

  if ! cmp -s "$path" "$path.new"; then
    mv -f "$path.new" "$path"
  fi
  rm -f "$path.new"
}

extra_bitbake_info()
{
  local package="$1"
  local output_path="$2"
  local tmpf="$output_path/bitbake.tmp"
  local envf="$output_path/bitbake.env"
  local ret
  bitbake -e -b "$package" > "$tmpf" 2>&1
  ret=$?
  if [ $ret -eq 0 ]; then
    # Extract the license extra information
    egrep '^(LICENSE=|SUMMARY=|HOMEPAGE=|PV=|PN=|PR=|PF=)' "$tmpf" > "$envf"
  fi
  rm -f "$tmpf"
  return $ret
}

## Setup the yocto source archiver
## PATH: The path to local.conf
## ARCHIVER: The bitbake archiver source mode to install.  One of
##           original patched configured.
##
## Refer to the bitbake documentation for details of the archiver:
## https://github.com/openembedded/openembedded-core/blob/master/meta/classes/archiver.bbclass
##

setup_archiver()
{
  local path="$1"
  local archiver="$2"
  local name="build-mbl-archiver"

  # We need to modify the local.conf file to inherit the archiver
  # class then configure the archiver behaviour.

  # The local.conf modification should be indempotent and handle the
  # situation that consecutive builds (and hence consecutive calls to
  # this setup function) change the archiver configuration, or indeed,
  # remove the configuration.
  #
  # We achieve this by putting start and end markers around the
  # configuration we inject.  We then implement a 3 stage processes:
  # 1) Remove any existing marked configuration
  # 2) Add the new required configuration, if any.
  # 3) Atomically update the local.conf file with the new file if
  #    anything changed.
  #
  # The atomic update ensures that if we fail, or are interrupted, we
  # never leave a partially updated local.conf.  Atomic update is not
  # because another process might race us!

  # If we previously aborted we may have left a working temporary file
  # littering the work area.
  rm -f "$path.new"

  # Remove any existing marked configuration.
  awk '/^# start '"$name"'$/ { drop = 1; next }
       /^# stop '"$name"'$/  { drop = 0; next }
       drop                  { next }
                             { print }' "$path" > "$path.new"

  # Add the new required configuration, if any.
  if [ -n "${archiver}" ]; then
    cat >> "$path.new" <<EOF
# start build-mbl-archiver
INHERIT += "archiver"
ARCHIVER_MODE[src] = "$archiver"
# stop build-mbl-archiver
EOF
  fi

  # If anything changed then atomically update local.conf
  if ! cmp -s "$path" "$path.new"; then
    mv -f "$path.new" "$path"
  fi
  rm -f "$path.new"
}

usage()
{
  cat <<EOF

usage: build.sh [OPTION] [STAGE]..

  --archive-source      Enable source package archiving.
  -j, --jobs NUMBER     Set the number of parallel processes. Default # CPU on the host.
  --branch BRANCH       Name the branch to checkout. Default ${default_branch}.
  --[no-]compress       Enable image artifact compression, default enabled.
  --builddir DIR        Use DIR for build, default CWD.
  --build-tag TAG       Specify a unique version tag to identify the build.
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
flag_archiver=""
flag_licenses=0

args=$(getopt -o+hj:o:x -l archive-source,branch:,builddir:,build-tag:,compress,no-compress,downloaddir:,external-manifest:,help,image:,inject-mcc:,jobs:,licenses,machine:,manifest:,outputdir:,url: -n "$(basename "$0")" -- "$@")
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
  --archive-source)
    flag_archiver=original
    ;;

  --branch)
    opt_prev=branch
    ;;

  --builddir)
    opt_prev=builddir
    ;;

  --build-tag)
    opt_prev=build_tag
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

  --licenses)
    flag_licenses=1
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

       if [ -n "${build_tag:-}" ]; then
         define_conf "$builddir/machine-$machine/mbl-manifest/layers/meta-mbl/conf/distro/mbl.conf" \
                     "DISTRO_VERSION" "$build_tag"
       fi
       setup_archiver "$builddir/machine-$machine/mbl-manifest/conf/local.conf" "$flag_archiver"

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

       # If outputdir is specified, the output of bitbake -e is saved in the
       # machine artifact directory. This command will output the configuration
       # files and the class files used in the execution environment.
       if [ -n "${outputdir:-}" ]; then
         machinedir="$outputdir/machine/$machine"
         mkdir -p "$machinedir"
         bitbake -e > bitbake-e.log.t
         mv -f bitbake-e.log.t "$machinedir/bitbake-e.log"
       fi

       # images is a space separated list of options, it should not be
       # quoted because it will form multiple options rather than one
       # option. However ideally each option in the list should be
       # quoted.
       # shellcheck disable=SC2086
       bitbake $images

       if [ "$flag_licenses" -eq 1 ]; then
         # Create extra bitbake info
         bblicenses="$builddir/machine-$machine/mbl-manifest/build-mbl/tmp-$distro-glibc/deploy/licenses"
         packages=$(ls -1 "$bblicenses")
         for pkg in $packages; do
           printf "%s: retrieving extra bitbake package info\n" "$pkg"
           # Package name without native extension
           pn=${pkg/-native/}
           if [ -f "$bblicenses/$pkg/recipeinfo" ]; then
             # Check for PN exceptions (replacing the package name if found)
             pn=${license_package_exceptions[$pn]:-$pn}
             # Make full package version name (to match bb file)
             pvstr=$(egrep '^PV:' "$bblicenses/$pkg/recipeinfo")
             pvn="${pn}_${pvstr/PV: /}"
             # Check for PVN exceptions (replacing the package version name if found)
             pvn=${license_package_exceptions[$pvn]:-$pvn}
             set +e
             if ! extra_bitbake_info "$pvn" "$bblicenses/$pkg"; then
               # Try again with just package name
               if ! extra_bitbake_info "$pn" "$bblicenses/$pkg"; then
                  printf "warning: could not retrieve extra bitbake info for %s (in %s)\n" "$pkg" "$bblicenses" >&2
               fi
             fi
             set -e
           else
             printf "note: ignoring package %s as no recipeinfo\n" "$pkg" >&2
           fi
         done
       fi
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
          imx7s-warp-mbl)
            suffixes="manifest tar.xz wic.gz"
            ;;
          raspberrypi3)
            suffixes="manifest tar.xz wic.gz"
            ;;
          esac

          # Source tar balls
          mkdir -p "$imagedir/source"

          case $flag_archiver in
          "")
            ;;
          original)
            # If we are archiving 'original' source we need to tar up a
            # directory containing source tarballs, patches, series
            # files and other crud.
            for path in "$bbtmpdir/deploy/sources/arm-oe-linux-gnueabi/"*; do
              dir=$(dirname "$path")
              pvn=$(basename "$path")
              write_info "save artifact %s\n" "$pvn"
              tar c -J -C "$dir" -f "$imagedir/source/$pvn.tar.xz" "$pvn"
            done
            ;;
          *)
            printf "assert: bad archiver %s\n" "$flag_archiver" >&2
            exit 9
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
