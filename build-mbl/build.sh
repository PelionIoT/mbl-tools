#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

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
  unset 'stages[0]'
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

all_machines="imx7s-warp-mbl raspberrypi3-mbl imx7d-pico-mbl imx8mmevk-mbl"

default_manifest="default.xml"
default_url="git@github.com:ARMmbed/mbl-manifest.git"
default_distro="mbl"
default_images="mbl-image-development"
default_accept_eula_machines=""
default_lic_cmp_build_tag=""
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

should_compress()
{
  [ "$flag_compress" -eq 1 ]
}

compress_extension()
{
  if should_compress; then
    echo ".gz"
  fi
}

maybe_compress()
{
    local path="$1"

    rm -f "$path.gz"
    if should_compress; then
        write_info "compress artifact %s\n" "$(basename "$path")"
        gzip "$path"
    fi
}

bitbake_env_setup() {
  machine=$1
  export_eula_env_vars "${machine}"
  cd "$builddir/machine-$machine/mbl-manifest"
  set +u
  set +e
  # shellcheck disable=SC1091
  MACHINE="$machine" DISTRO="$distro" . setup-environment "build-mbl"
  # shellcheck disable=SC2181
  if [ $? -ne 0 ]; then
      exit 1
  fi
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
COPYLEFT_LICENSE_INCLUDE = "*"
# stop build-mbl-archiver
EOF
  fi

  # If anything changed then atomically update local.conf
  if ! cmp -s "$path" "$path.new"; then
    mv -f "$path.new" "$path"
  fi
  rm -f "$path.new"
}

create_binary_release()
{
  local image=${1:?Missing image parameter of ${FUNCNAME[0]}}
  local machine=${2:?Missing machine parameter of ${FUNCNAME[0]}}

  local artifact_machine_dir="${outputdir}/machine/${machine}"
  local artifact_image_dir="${artifact_machine_dir}/images/${image}"

  create_binary_release_readme "$image" "$machine"

  declare -a lic_manifest_files
  lic_manifest_files+=(license.manifest)
  lic_manifest_files+=(image_license.manifest)

  # Initramfs manifest files are optional - we don't have an initramfs on some
  # platforms
  if [ -e "${artifact_image_dir}/initramfs-license.manifest" ]; then
    lic_manifest_files+=(initramfs-license.manifest)
  fi
  if [ -e "${artifact_image_dir}/initramfs-image_license.manifest" ]; then
    lic_manifest_files+=(initramfs-image_license.manifest)
  fi

  local release_archive_name="${build_tag:-mbl-os}-${machine}-release.tar"

  # If you add files to the binary release archive, please update
  # README.binary_release_template
  tar -c -f "${artifact_image_dir}/${release_archive_name}" \
    -C "${artifact_image_dir}/images" \
      "${image}-${machine}.wic.gz" \
      "${image}-${machine}.wic.bmap" \
    -C "${artifact_image_dir}" \
      source \
      "${lic_manifest_files[@]}" \
      README \
    -C "${artifact_machine_dir}" \
      "licenses.tar$(compress_extension)" \
    -C  "$outputdir" \
      pinned-manifest.xml \
      buildinfo.txt
}

create_binary_release_readme()
{
  local image=${1:?Missing image parameter of ${FUNCNAME[0]}}
  local machine=${2:?Missing machine parameter of ${FUNCNAME[0]}}

  local artifact_image_dir="${outputdir}/machine/${machine}/images/${image}"

  sed \
    -e "s|__REPLACE_ME_WITH_IMAGE__|$image|g" \
    -e "s|__REPLACE_ME_WITH_MACHINE__|$machine|g" \
    -e "s|__REPLACE_ME_WITH_COMPRESS_EXTENSION__|$(compress_extension)|g" \
    "${execdir}/README.binary_release_template" > "${artifact_image_dir}/README"

  case "$machine" in
    imx8mmevk-mbl|imx7d-pico-mbl)
      cat "${execdir}/Licensing_and_Acknowledgment.template_nxp" >> "${artifact_image_dir}/README"
      ;;
    *)
      ;;
  esac

}

create_license_report()
{
  local build_lic_paths=${1:?Missing license-paths parameter of ${FUNCNAME[0]}}
  local prev_build_tag="$2"
  local api_key="$3"
  local html_output_dir=${4:?Missing html_output_dir parameter of ${FUNCNAME[0]}}
  local machines=${5:?Missing machines parameter of ${FUNCNAME[0]}}

  "./license_diff_report.py" "$build_tag" \
                             --lics-to-review "$build_lic_paths" \
                             --lics-to-compare "$prev_build_tag" \
                             --images "$images" \
                             --machines "$machines" \
                             --apikey "$api_key" \
                             --html "$html_output_dir"

  mkdir -p "$outputdir/license-reports"
  # Copy the HTML report(s) to the artifact dir
  mv "$html_output_dir/"*.manifest.html "$outputdir/license-reports"
}

find_license_manifest_dir()
{
  local image=${1:?Missing image parameter of ${FUNCNAME[0]}}
  local machine=${2:?Missing machine parameter of ${FUNCNAME[0]}}

  local licdir="$builddir/machine-$machine/mbl-manifest/build-mbl/tmp-$distro-glibc/deploy/licenses"
  local license_manifest_dir_pattern="${image}-${machine}-*"

  local license_manifest_dir
  license_manifest_dir=$(find "$licdir" -maxdepth 1 -type d -name "$license_manifest_dir_pattern")
  local count
  count=$(printf "%s" "$license_manifest_dir" | wc -w)
  if [ "$count" -ne 1 ]; then
    printf "error: found unexpected number of files matching \"%s\" in %s (%d)" \
      "$license_manifest_dir_pattern" \
      "$licdir" \
      "$count" \
      1>&2
    return 1
  fi

  printf "%s" "${license_manifest_dir}"
}

artifact_image_manifests()
{
  local image=${1:?Missing image parameter of ${FUNCNAME[0]}}
  local machine=${2:?Missing machine parameter of ${FUNCNAME[0]}}

  local artifact_image_dir="${outputdir}/machine/${machine}/images/${image}"

  local license_manifest_dir
  license_manifest_dir=$(find_license_manifest_dir "$image" "$machine")
  cp "${license_manifest_dir}/license.manifest" "${artifact_image_dir}/license.manifest"
  cp "${license_manifest_dir}/image_license.manifest" "${artifact_image_dir}/image_license.manifest"
  cp "${license_manifest_dir}/image_license.manifest.json" "${artifact_image_dir}/image_license.manifest.json"
  cp "${license_manifest_dir}/license.manifest.json" "${artifact_image_dir}/license.manifest.json"
  # Don't exit (due to "set -e") if we can't find initramfs image license
  # manifests - we may not have an initramfs image on some platforms
  local initramfs_license_manifest_dir
  if initramfs_license_manifest_dir=$(find_license_manifest_dir mbl-image-initramfs "$machine"); then
    cp "${initramfs_license_manifest_dir}/license.manifest" "${artifact_image_dir}/initramfs-license.manifest"
    cp "${initramfs_license_manifest_dir}/image_license.manifest" "${artifact_image_dir}/initramfs-image_license.manifest"
    cp "${initramfs_license_manifest_dir}/license.manifest.json" "${artifact_image_dir}/initramfs-license.manifest.json"
    cp "${initramfs_license_manifest_dir}/image_license.manifest.json" "${artifact_image_dir}/initramfs-image_license.manifest.json"
  fi
}

artifact_build_info()
{
  [ -n "$outputdir" ] || return 0

  local script_name
  script_name=$(basename "$0")
  local buildinfo_path="${outputdir}/buildinfo.txt"
  local buildinfo_tmppath="${buildinfo_path}.tmp"

  rm -f "${buildinfo_tmppath}"

  if [ -n "${parent_command_line:-}" ]; then
    printf "%s parent command line: [%s]\n\n" "$script_name" "${parent_command_line}" >> "${buildinfo_tmppath}"
  fi

  printf "%s command line: [%s]\n\n" "$script_name" "${command_line}" >> "${buildinfo_tmppath}"

  if [ -n "${mbl_tools_version:-}" ]; then
    printf "mbl-tools version: %s\n\n" "$mbl_tools_version" >> "${buildinfo_tmppath}"
  fi

  mv "${buildinfo_tmppath}" "${buildinfo_path}"
}

# Function used to export the ACCEPT_EULA_machine-name environment
# variable to be consumed by the setup-environment-internal from mbl-config
export_eula_env_vars() {
    local machine="$1"

    # Iterate over the accept_eulas list and only export the ACCEPT_EULA_machine-name environment
    # variable if the passed machine is in this list.
    for accept_eula_machine in $accept_eulas; do
        if [ "$machine" == "$accept_eula_machine" ]; then
            export "ACCEPT_EULA_$(printf "%s" "${machine%-mbl}" | sed 's/-//g')=1"
        fi
    done
}

usage()
{
  cat <<EOF

usage: build.sh [OPTION] [STAGE]..

MANDATORY parameters:
  --branch BRANCH       Name the mbl-manifest branch to checkout.
  --machine MACHINE     Yocto MACHINE to build. Repeat --machine option to build more
                        than one machine.
                        Supported machines: $all_machines.
  --builddir DIR        Use DIR for build.

OPTIONAL parameters:
  --accept-eula MACHINE Automatically accept any EULAs required for building MACHINE.
                        Repeat the --accept-eula option to accept EULAs for
                        more than one MACHINE.
  --archive-source      Enable source package archiving.
  --binary-release      Enable creation of a binary release archive. This
                        option implies --licenses and --archive-source.
  -j, --jobs NUMBER     Set the number of parallel processes. Default # CPU on the host.
  --[no-]compress       Enable image artifact compression, default enabled.
  --build-tag TAG       Specify a unique version tag to identify the build.
  --downloaddir DIR     Use DIR to store downloaded packages.
  --external-manifest PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --image IMAGE         Select an alternative image.  Default $default_images.
                        This option can be repeated to add multiple images.
  --inject-mcc PATH     Add a file to the list of mbed cloud client files
                        to be injected into a build.  This is a temporary
                        mechanism to inject development keys.
  --licenses            Collect extra build license info. Default disabled.
  --manifest MANIFEST   Name the manifest file. Default ${default_manifest}.
  --mbl-tools-version STRING
                        Specify the version of mbl-tools that this script came
                        from. This is written to buildinfo.txt in the output
                        directory.
  -o, --outputdir PATH  Directory to output build artifacts. Mandatory if
                        --binary-release is given.
  --parent-command-line STRING
                        Specify the command line that was used to invoke the
                        script that invokes build.sh. This is written to
                        buildinfo.txt in the output directory.
  --url URL             Name the URL to clone. Default ${default_url}.
  -x                    Enable shell debugging in this script.

  STAGE                 Start execution at STAGE, default previous
                        exit stage or start.

Useful STAGE names:
  clean                 Blow away the working tree and start over.
  start                 Start at the beginning.
  build                 Execute the bitbake build for all images and machines.
  interactive           Launch interactive mode to run BitBake and associated
                        commands.

EOF
}

url="$default_url"
distro="$default_distro"
flag_compress=1
flag_archiver=""
flag_licenses=0
flag_binary_release=0
flag_interactive_mode=0

# Save the full command line for later - when we do a binary release we want a
# record of how this script was invoked
command_line="$(printf '%q ' "$0" "$@")"

args=$(getopt -o+hj:o:x -l accept-eula:,archive-source,artifactory-api-key:,binary-release,branch:,builddir:,build-tag:,compress,no-compress,downloaddir:,external-manifest:,help,image:,inject-mcc:,jobs:,licenses,licenses-buildtag:,machine:,manifest:,mbl-tools-version:,outputdir:,parent-command-line:,url: -n "$(basename "$0")" -- "$@")
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
  --accept-eula)
    opt_append=accept_eulas
    ;;

  --archive-source)
    flag_archiver=original
    ;;

  --artifactory-api-key)
    opt_prev=artifactory_api_key
    ;;

  --binary-release)
    flag_binary_release=1
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

  --mbl-tools-version)
    opt_prev=mbl_tools_version
    ;;

  --no-compress)
    flag_compress=0
    ;;

  --parent-command-line)
      opt_prev=parent_command_line
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

  --licenses-buildtag)
    opt_prev=lic_cmp_build_tag
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

if [ -n "${external_manifest:-}" ] && [ -n "${manifest:-}" ]; then
  printf "error: --external-manifest and --manifest are mutually exclusive.\n" >&2
  exit 3
fi

if [ "$flag_licenses" -eq 1 ]; then
  if [ -z "${artifactory_api_key:-}" ]; then
    printf "error: --licenses also requires --artifactory-api-key \n" >&2
    exit 3
  fi
  if [ -z "${build_tag:-}" ]; then
      printf "error: --licenses also requires --build_tag\n" >&2
      exit 3
  fi
fi

if [ -z "${lic_cmp_build_tag:-}" ]; then
  lic_cmp_build_tag="$default_lic_cmp_build_tag"
fi

if [ -z "${branch:-}" ]; then
  printf "error: missing --branch BRANCH parameter\n" >&2
  exit 3
fi

if [ -z "${manifest:-}" ]; then
  manifest="$default_manifest"
fi

if [ $# -gt 0 ]; then
  stages=("$@")
fi

if [ -n "${builddir:-}" ]; then
  builddir="$(readlink -f "$builddir")"
  if [ ! -d "$builddir" ]; then
    printf "error: --builddir '%s' directory doesn't exist.\n" "$builddir" >&2
    exit 3
  fi
else
  printf "error: missing --builddir PATH parameter.\n" >&2
  exit 3
fi

if [ -z "${images:-}" ]; then
  images="$default_images"
fi

if [[ ${images} == *"mbl-image-production"* ]]; then
    printf "error: mbl-image-production not supported in this release.\n" >&2
    exit 3
fi

if [ -z "${machines:-}" ]; then
  printf "error: missing --machine MACHINE parameter. Supported machines: '%s'.\n" "$all_machines" >&2
  exit 3
fi

if [ -z "${accept_eulas:-}" ]; then
  accept_eulas="$default_accept_eula_machines"
fi

for machine in $machines $accept_eulas; do
  if ! valid_machine_p "$machine"; then
    printf "error: unrecognized machine '%s'. Supported machines: '%s'.\n" "$machine" "$all_machines" >&2
    exit 3
  fi
done

if [ -n "${outputdir:-}" ]; then
  outputdir="$(readlink -f "$outputdir")"
fi

if [ "${flag_binary_release}" -eq 1 ]; then
    flag_licenses=1
    flag_archiver=original
    if [ -z "$outputdir" ]; then
        printf "error: --outputdir option is mandatory when --binary-release is specified\n" >&2
        exit 3
    fi
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
    # Replace the manifest if a custom one is provided
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
     repo --no-pager manifest -r -o "$builddir/pinned-manifest.xml"
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

    if [ "${flag_interactive_mode}" -eq 1 ]; then
      push_stages interactive
    else
      push_stages setup
    fi
    ;;

  setup)
    for machine in $machines; do
      (cd "$builddir/machine-$machine/mbl-manifest"
       export_eula_env_vars "${machine}"
       set +u
       set +e
       # shellcheck disable=SC1091
       MACHINE="$machine" DISTRO="$distro" . setup-environment "build-mbl"
       # shellcheck disable=SC2181
       if [ $? -ne 0 ]; then
           exit 1
       fi
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
       (
       bitbake_env_setup "$machine"
       if [ -n "${build_tag:-}" ]; then
         define_conf "$builddir/machine-$machine/mbl-manifest/layers/meta-mbl/meta-mbl-distro/conf/distro/mbl.conf" \
                     "DISTRO_VERSION" "$build_tag"
       fi
       if [ "${flag_binary_release}" -eq 1 ]; then
         echo "MACHINE_FEATURES_remove += \"qca9377-bin\"" >> "$builddir/machine-$machine/mbl-manifest/conf/local.conf"
       fi
       setup_archiver "$builddir/machine-$machine/mbl-manifest/conf/local.conf" "$flag_archiver"

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
            suffixes="manifest tar.xz wic.gz wic.bmap"
            targetsys=arm-oe-linux-gnueabi
            ;;
          raspberrypi3-mbl)
            suffixes="manifest tar.xz wic.gz wic.bmap"
            targetsys=arm-oe-linux-gnueabi
            ;;
          imx7d-pico-mbl)
            suffixes="manifest tar.xz wic.gz wic.bmap"
            targetsys=arm-oe-linux-gnueabi
            ;;
          imx8mmevk-mbl)
            suffixes="manifest tar.xz wic.gz wic.bmap"
            targetsys=aarch64-oe-linux
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
            for path in "$bbtmpdir/deploy/sources/$targetsys/"*; do
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

          # License manifests
          artifact_image_manifests "$image" "$machine"
        done

        # ... the license information...
        write_info "save artifact licenses\n"
        tar c -C "$bbtmpdir/deploy" -f "$machinedir/licenses.tar" "licenses"

        if [ "$flag_licenses" -eq 1 ]; then
          write_info "create license report\n"
          for image in $images; do
            for mach in $machines; do
              # use the license manifests we just copied to the artifact dir
              build_lic_paths+="${outputdir}/machine/${mach}/images/${image}"
            done
          done

          create_license_report "$build_lic_paths" \
                                "$lic_cmp_build_tag" \
                                "$artifactory_api_key" \
                                "$outputdir" \
                                "$machines"
        fi

        maybe_compress "$machinedir/licenses.tar"
      done
      artifact_build_info

      if [ "$flag_binary_release" -eq 1 ]; then
        for machine in $machines; do
          for image in $images; do
            create_binary_release "$image" "$machine"
          done
        done
      fi

    fi
    ;;

  interactive)
    # Check the number of machines passed
    numof_machines=$(wc -w <<< "${machines}")
    if [ "$numof_machines" -gt 1 ]; then
      printf "error: interactive mode only supports on machine at a time.\n" >&2
      exit 3
    fi

    # Remove any spaces from the machines string
    machine="${machines//[[:blank:]]/}"

    # Check if the layers have been checked out before launching
    path_to_check="$builddir/machine-$machine/mbl-manifest/layers"
    if ! [ -d "${path_to_check}" ]; then
      flag_interactive_mode=1
      push_stages start
    else
      bitbake_env_setup "$machine"
      cat <<EOF

Welcome to interactive mode.
You can perform BitBake or repo commands. You can use the Yocto devtool
to modify a component. It is recommended you edit files outside of this
interactive shell. Any changes in the build directory ${builddir}
gets reflected in the interactive mode.
To exit interactive mode use the "exit" command.
For more information and examples please see the
"Developing Mbed Linux OS" section on the website:
https://os.mbed.com/docs/mbed-linux-os.

EOF
      exec env TERM=screen bash
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
