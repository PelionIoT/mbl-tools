#!/bin/bash

# Copyright (c) 2018-2019, Arm Limited and Contributors. All rights reserved.
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

# Load the config functions
source "$execdir/config-funcs.sh"

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

all_machines="imx7s-warp-mbl raspberrypi3-mbl imx7d-pico-mbl imx8mmevk-mbl imx6ul-pico-mbl imx6ul-des0258-mbl"

default_manifest="default.xml"
default_manifest_repo="git@github.com:ARMmbed/mbl-manifest.git"
default_distro="mbl-development"
default_image="mbl-image-development"
default_production_distro="mbl-production"
default_production_image="mbl-image-production"
default_accept_eula_machines=""
default_lic_cmp_artifact_path=""
default_mcc_destdir="build-$default_distro"

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
  MACHINE="$machine" DISTRO="$distro" . setup-environment "build-$distro"
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

inject_custom_data()
{
  local path="$1"
  local custom_data="$2"
  local name="$3"

  # We need to modify the local.conf file to inject custom string the user
  # specifies.

  # The modification should be indempotent and handle the
  # situation that consecutive builds (and hence consecutive calls to
  # this function) change the custom data, or indeed, remove it
  #
  # We achieve this by putting start and end markers around the
  # configuration we inject.  We then implement a 3 stage processes:
  # 1) Remove any existing marked configuration
  # 2) Add the new required configuration, if any.
  # 3) Atomically update the original file with the new file if
  #    anything changed.
  #
  # The atomic update ensures that if we fail, or are interrupted, we
  # never leave a partially updated original file.  Atomic update is not
  # because another process might race us!

  # If we previously aborted we may have left a working temporary file
  # littering the work area.
  rm -f "$path.new"

  # Remove any existing marked configuration.
  sed '/^# start '"$name"'$/,/^# stop '"$name"'$/d' "$path" > "$path.new"

  # Add the new required configuration, if any.
  if [ -n "${custom_data}" ]; then
    printf "# start %s\n%b\n# stop %s\n" "$name" "$custom_data" "$name" >> "$path.new"
  fi

  # Atomically update the file
  mv -f "$path.new" "$path"
}

setup_archiver()
{
  local path="$1"
  local archiver="$2"
  local name="build-$distro-archiver"
  local custom_data=""

  ## Setup the yocto source archiver
  ## PATH: The path to local.conf
  ## ARCHIVER: The bitbake archiver source mode to install.  One of
  ##           original patched configured.
  ##
  ## Refer to the bitbake documentation for details of the archiver:
  ## https://github.com/openembedded/openembedded-core/blob/master/meta/classes/archiver.bbclass

  # We need to modify the local.conf file to inherit the archiver
  # class then configure the archiver behaviour.
  if [ -n "${archiver}" ]; then
    custom_data=$(cat <<EOF
INHERIT += "archiver"
ARCHIVER_MODE[src] = "$archiver"
COPYLEFT_LICENSE_INCLUDE = "*"
EOF
)
  fi

  # Inject the data into the file
  inject_custom_data "$path" "$custom_data" "$name"
}

inject_local_conf_data()
{
  local path="$1"
  local custom_data="$2"
  local name="custom-data"

  # Inject the data into the file
  inject_custom_data "$path" "$custom_data" "$name"
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
    imx8mmevk-mbl)
      cat "${execdir}/Licensing_and_Acknowledgment.template_nxp" >> "${artifact_image_dir}/README"
      ;;
    *)
      ;;
  esac

}

create_license_report()
{
  set +u
  set +e
  local build_lic_paths=${1:?Missing license-paths parameter of ${FUNCNAME[0]}}
  # Assumption the path is of format: CONTEXT/mbed-linux/BUILD/BUILD-TAG
  local prev_artifact_tag="${2##*/}"      # Extract BUILD-TAG
  local prev_artifact_context="${2%%/*}"  # Extract CONTEXT
  local api_key="$3"
  local html_output_dir=${4:?Missing html_output_dir parameter of ${FUNCNAME[0]}}
  local machines=${5:?Missing machines parameter of ${FUNCNAME[0]}}
  local image=${6:?Missing images parameter of ${FUNCNAME[0]}}

  "./license_diff_report.py" "$build_tag" \
                             --lics-to-review "$build_lic_paths" \
                             --lics-to-compare "$prev_artifact_tag" \
                             --build-context "$prev_artifact_context" \
                             --images "$image" \
                             --machines "$machines" \
                             --apikey "$api_key" \
                             --html "$html_output_dir"

  mkdir -p "$outputdir/license-reports"
  # Copy the HTML report(s) to the artifact dir
  mv "$html_output_dir/"*.manifest.html "$outputdir/license-reports"
  set -u
  set -e
}

find_license_manifest_dir()
{
  local image=${1:?Missing image parameter of ${FUNCNAME[0]}}
  local machine=${2:?Missing machine parameter of ${FUNCNAME[0]}}

  local licdir="$builddir/machine-$machine/mbl-manifest/build-$distro/tmp/deploy/licenses"
  local license_manifest_dir_pattern="${image}-${machine}-*"
  # find the last modified license manifest directory as we could possibly have
  # multiple license directories after multiple build runs
  local license_manifest_dir
  if ! license_manifest_dir=$(find "$licdir" -maxdepth 1 -type d -name "$license_manifest_dir_pattern" -print0 | xargs -r -0 ls -1 -t -d | head -1); then
    printf "error: failed to find any directories matching \"%s\" in %s\n" \
      "$license_manifest_dir_pattern" \
      "$licdir" \
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

cat_files() {
    local files=("$@")

    for file in "${files[@]}";
    do
        printf "Printing the content of file: %s\n" "$file"
        cat "$file"
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
  --distro DISTRO       Specify the DISTRO to be set. Default $default_distro.
  --downloaddir DIR     Use DIR to store downloaded packages.
  --external-manifest PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --inject-key PATH     Add a file to the list of keys/certificates to be
                        injected into the build.
  --image IMAGE         Select an alternative image.  Default $default_image when
                        --distro $default_distro and default $default_production_image
                        when --distro $default_production_distro.
  --inject-mcc PATH     Add a file to the list of mbed cloud client files
                        to be injected into a build.  This is a temporary
                        mechanism to inject development keys. Mandatory if passing
                        --mcc-destdir parameter.
  --mcc-destdir PATH    Relative directory from "layers" dir to where the file(s)
                        passed with --inject-mcc should be copied to.
  --licenses            Collect extra build license info. Default disabled.
  --licenses-artifact-path PATH
                        Artifact path to compare the licenses against, e.g.
                        isg-mbed-linux-release/mbed-linux/mbl-os-0.7.0/mbl-os-0.7.0_build5
  --local-conf-data STRING
                        Data to append to local.conf.
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
  --repo-host NAME      Add a trusted git repository host to the build
                        environment. Can be specified multiple times.
  --root-passwd-file PATH
                        The file containing the root user password in plain text.
  --ssh-auth-keys PATH
                        Path to the SSH Authorized Keys file to be installed
                        in the target rootfs at /home/user/.ssh/authorized_keys.
                        The filename must be prefixed with "user_".
  --manifest-repo URL   Name the manifest URL to clone. Default ${default_manifest_repo}.
  --url           URL   Name the manifest URL to clone. Default ${default_manifest_repo}.
                        Deprecated. Use --manifest-repo instead.
  -x                    Enable shell debugging in this script.

  STAGE                 Start execution at STAGE, default previous
                        exit stage or start.

Useful STAGE names:
  clean                 Blow away the working tree and start over.
  start                 Start at the beginning.
  build                 Execute the bitbake build for the specified image on
                        all machines.
  interactive           Launch interactive mode to run BitBake and associated
                        commands.

EOF
}

manifest_repo=""
url=""
mcc_final_destdir="$default_mcc_destdir"
flag_compress=1
flag_archiver=""
local_conf_data=""
flag_licenses=0
flag_binary_release=0
flag_interactive_mode=0
repo_hosts=""

# Find the build directory option - where the config resides
config_dir=$(config_locate_dir "$@")
# Get the arguments saved in the config (if any)
config_build=()
config_read "$config_dir" "build.args" config_build

# Save the full command line for later - when we do a binary release we want a
# record of how this script was invoked
if [ ${#config_build[@]} -gt 0 ]; then
  command_line="$(printf '%q ' "$0" "${config_build[@]}" "$@")"
else
  command_line="$(printf '%q ' "$0" "$@")"
fi

args_list="accept-eula:,archive-source,artifactory-api-key:"
args_list="${args_list},binary-release,branch:,builddir:,build-tag:"
args_list="${args_list},compress"
args_list="${args_list},distro:,downloaddir:"
args_list="${args_list},external-manifest:"
args_list="${args_list},help"
args_list="${args_list},image:,inject-key:,inject-mcc:"
args_list="${args_list},jobs:"
args_list="${args_list},licenses,licenses-artifact-path:,local-conf-data:"
args_list="${args_list},machine:,manifest:,manifest-repo:,mbl-tools-version:"
args_list="${args_list},mcc-destdir:"
args_list="${args_list},no-compress"
args_list="${args_list},outputdir:"
args_list="${args_list},parent-command-line:"
args_list="${args_list},repo-host:,root-passwd-file:"
args_list="${args_list},ssh-auth-keys:"
args_list="${args_list},url:"

if [ ${#config_build[@]} -gt 0 ]; then
  args=$(getopt -o+hj:o:x -l $args_list -n "$(basename "$0")" -- "${config_build[@]}" "$@")
else
  args=$(getopt -o+hj:o:x -l $args_list -n "$(basename "$0")" -- "$@")
fi
eval set -- "$args"

# Save the arguments for later in an array to write out as parsing will
# remove the arguments
args_saved=()
config_save_args args_saved "$@"

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

  --distro)
    opt_prev=distro
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
    opt_prev=image
    ;;

  --inject-key)
    opt_append=inject_key_files
    ;;

  --inject-mcc)
    opt_append=inject_mcc_files
    ;;

  --mcc-destdir)
    opt_prev=mcc_destdir
    ;;

  -j | --jobs)
    opt_prev=flag_jobs
    ;;

  --licenses)
    flag_licenses=1
    ;;

  --licenses-artifact-path)
    opt_prev=lic_cmp_artifact_path
    ;;

  --local-conf-data)
    opt_prev=local_conf_data
    ;;

  --machine)
    opt_append=machines
    ;;

  --manifest)
    opt_prev=manifest
    ;;

  --manifest-repo)
    opt_prev=manifest_repo
    ;;
  -o | --outputdir)
    opt_prev=outputdir
    ;;

  --repo-host)
    opt_append=repo_hosts
    ;;

  --root-passwd-file)
    opt_prev=root_passwd_file
    ;;

  --ssh-auth-keys)
    opt_append=ssh_auth_keys
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

if [ -z "${lic_cmp_artifact_path:-}" ]; then
  lic_cmp_artifact_path="$default_lic_cmp_artifact_path"
fi

if [ -z "${branch:-}" ]; then
  printf "error: missing --branch BRANCH parameter\n" >&2
  exit 3
fi

if [ -n "${url:-}" ]; then
  printf "warning: --url is deprecated, use --manifest-repo\n" >&2
  if [ -z "${manifest_repo:-}" ]; then
    manifest_repo="$url"
  fi
fi

if [ -z "${manifest_repo:-}" ]; then
  manifest_repo="$default_manifest_repo"
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

if [ -z "${distro:-}" ]; then
  distro="$default_distro"
fi

if [ -z "${image:-}" ]; then
  if [ "${distro:-}" ==  "$default_distro" ]; then
      image="$default_image"
  elif [ "${distro:-}" ==  "$default_production_distro" ]; then
      image="$default_production_image"
  else
    printf "error: missing --image IMAGE parameter.\n" >&2
    exit 3
  fi
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

if [ -n "${mcc_destdir:-}" ]; then
  if [ -z "${inject_mcc_files:-}" ]; then
      printf "error: --mcc-destdir requires at least one --inject-mcc parameter.\n" >&2
      exit 3
  fi
  mcc_final_destdir="layers/$mcc_destdir"
fi

# After all the validation, write out a config (if there isn't one)
config_write "$config_dir" "build.args" "${args_saved[@]}"

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
"$execdir/ssh-setup.sh" $repo_hosts

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
      repo_init_atomic "$builddir/mbl-manifest" -u "$manifest_repo" -b "$branch" -m "$manifest"
    fi

    # If we are saving build artifacts, then save them as they are
    # created rather than waiting for the end of the build process,
    # this makes debug of build issues easier.
    if [ -n "${outputdir:-}" ]; then
      cp "$builddir/mbl-manifest/.repo/manifest.xml" "$outputdir/manifest.xml"
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
        repo_init_atomic "$builddir/machine-$machine/mbl-manifest" -u "$manifest_repo"
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
       MACHINE="$machine" DISTRO="$distro" . setup-environment "build-$distro"
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
    if [ -n "${inject_key_files:-}" ]; then
      for machine in $machines; do
        for file in $inject_key_files; do
          base="$(basename "$file")"
          cp "$file" "$builddir/machine-$machine/mbl-manifest/build-$distro/$base"
        done
      done
    fi

    if [ -n "${inject_mcc_files:-}" ]; then
      for machine in $machines; do
        for file in $inject_mcc_files; do
          base="$(basename "$file")"
          cp "$file" "$builddir/machine-$machine/mbl-manifest/$mcc_final_destdir/$base"
        done
      done
    fi

    if [ -n "${root_passwd_file:-}" ]; then
      for machine in $machines; do
          cp "$root_passwd_file" "$builddir/machine-$machine/mbl-manifest/build-$distro/mbl_root_passwd_file"
      done
    fi

    if [ -n "${ssh_auth_keys:-}" ]; then
      for machine in $machines; do
        for file in $ssh_auth_keys; do
          base="$(basename "$file")"
          cp "$file" "$builddir/machine-$machine/mbl-manifest/build-$distro/$base"
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
         define_conf "$builddir/machine-$machine/mbl-manifest/layers/meta-mbl/meta-mbl-distro/conf/distro/include/mbl-distro.inc" \
                     "DISTRO_VERSION" "$build_tag"
       fi
       if [ "${flag_binary_release}" -eq 1 ]; then
         echo "MACHINE_FEATURES_remove += \"qca9377-bin\"" >> "$builddir/machine-$machine/mbl-manifest/conf/local.conf"
       fi

       setup_archiver "$builddir/machine-$machine/mbl-manifest/conf/local.conf" "$flag_archiver"

       inject_local_conf_data "$builddir/machine-$machine/mbl-manifest/conf/local.conf" "$local_conf_data"

       # If outputdir is specified, the output of bitbake -e is saved in the
       # machine artifact directory. This command will output the configuration
       # files and the class files used in the execution environment.
       if [ -n "${outputdir:-}" ]; then
         machinedir="$outputdir/machine/$machine"
         mkdir -p "$machinedir"
         bitbake -e > bitbake-e.log.t
         mv -f bitbake-e.log.t "$machinedir/bitbake-e.log"
       fi

       # Print out the content of the manifest and pinned manifest files.
       # This is useful to have at the log level that we are building.
       cat_files "$builddir/mbl-manifest/.repo/manifest.xml" "$builddir/pinned-manifest.xml"

       printf "\nCalling: bitbake %s\n\n" "$image"
       bitbake "$image"
      )
    done
    push_stages artifact
    ;;

  artifact)
    if [ -n "${outputdir:-}" ]; then
      for machine in $machines; do
        bbbuilddir="$builddir/machine-$machine/mbl-manifest/build-$distro"
        bbtmpdir="${bbbuilddir}/tmp"
        machinedir="$outputdir/machine/$machine"
        imagedir="$machinedir/images/$image"

        # We are interested in the image...
        mkdir -p "$imagedir/images"

        # Relevant to all machines
        suffixes="manifest tar.xz wic.gz wic.bmap"

        case $machine in
        raspberrypi3-mbl) ;& # fall-through
        imx7s-warp-mbl)   ;& # fall-through
        imx7d-pico-mbl)   ;& # fall-through
        imx6ul-pico-mbl)  ;& # fall-through
        imx6ul-des0258-mbl)
          targetsys=arm-oe-linux-gnueabi
          ;;
        imx8mmevk-mbl)
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
        bh_path="$builddir/machine-$machine/mbl-manifest/build-$distro/buildhistory/images/${machine//-/_}/glibc/$image"
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

        # Images Sign Keys
        mkdir -p "$imagedir/keys/"
        shopt -s nullglob
        for file in "$bbtmpdir/deploy/images/$machine/"*.{pem,crt,key} ; do
            write_info "save artifact %s\n" "$(basename "$file")"
            cp "$file" "$imagedir/keys/"
        done
        shopt -u nullglob

        # License manifests
        artifact_image_manifests "$image" "$machine"

        # local.conf
        write_info "save artifact local.conf\n"
        cp "${bbbuilddir}/conf/local.conf" "$machinedir"

        # ... the license information...
        write_info "save artifact licenses\n"
        tar c -C "$bbtmpdir/deploy" -f "$machinedir/licenses.tar" "licenses"

        if [ "$flag_licenses" -eq 1 ]; then
          write_info "create license report\n"
          for mach in $machines; do
            # use the license manifests we just copied to the artifact dir
            build_lic_paths+="${outputdir}/machine/${mach}/images/${image}"
          done

            create_license_report "$build_lic_paths" \
                                  "$lic_cmp_artifact_path" \
                                  "$artifactory_api_key" \
                                  "$outputdir" \
                                  "$machines" \
                                  "$image"
        fi

        maybe_compress "$machinedir/licenses.tar"
      done
      artifact_build_info

      if [ "$flag_binary_release" -eq 1 ]; then
        for machine in $machines; do
          create_binary_release "$image" "$machine"
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
