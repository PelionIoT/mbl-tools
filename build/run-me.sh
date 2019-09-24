#!/bin/bash

# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

set -e
set -u

execdir="$(readlink -e "$(dirname "$0")")"

default_imagename="mbl-manifest-env"
default_containername="mbl-tools-container.$$"
default_project="mbl"

trap cleanup 0

cleanup() {
    # This command will return an id (eg. 43008e2a9f5a) of the running
    # container
    running_container="$(docker ps -q -f name="$default_containername")"
    if [ ! -z "$running_container" ]; then
        docker kill "$default_containername"
    fi
}

build_script_for_project() {
    project=${1:?}
    case "$1" in
        build-update-payloads)
            printf "%s\n" "build-update-payloads.py"
            ;;
        mbl)
            printf "%s\n" "build.sh"
            ;;
        poky)
            printf "%s\n" "build-poky.py"
            ;;
        *)
            printf "Unrecognized project \"%s\"" "$project" >&2
            exit 5
            ;;
    esac
}

dockerfile_for_project() {
    project=${1:?}
    case "$1" in
        build-update-payloads)
            printf "%s\n" "common/Dockerfile"
            ;;
        mbl)
            printf "%s\n" "common/Dockerfile"
            ;;
        poky)
            printf "%s\n" "common/Dockerfile"
            ;;
        *)
            printf "Unrecognized project \"%s\"" "$project" >&2
            exit 5
            ;;
    esac
}

usage()
{
  cat <<EOF

usage: run-me.sh [OPTION] -- [build.sh arguments]

MANDATORY parameters:
  --builddir PATH       Specify the root of the build tree.

OPTIONAL parameters:
  --boot-rot-key PATH   Path to the secure world root of trust private key. If
                        this option is not used, either a new key will be
                        generated, or a key generated for a previous build in
                        the same work area will be used.
  --downloaddir PATH    Use PATH to store Yocto downloaded sources.
  --external-manifest PATH
                        Specify an external manifest file.
  -h, --help            Print brief usage information and exit.
  --image-name NAME     Specify the docker image name to build. Default ${default_imagename}.
  --inject-mcc PATH     Add a file to the list of mbed cloud client files
                        to be injected into a build.  This is a temporary
                        mechanism to inject development keys.  Mandatory if passing
                        --mcc-destdir parameter.
  --kernel-rot-crt PATH Path to the normal world root of trust public key
                        certificate. If this option is not used, either a new
                        certificate will be generated, or a certificate
                        generated for a previous build in the same work area
                        will be used.
  --kernel-rot-key PATH Path to the normal world root of trust private key. If
                        this option is not used, either a new key will be
                        generated, or a key generated for a previous build in
                        the same work area will be used.
  --mcc-destdir PATH    Relative directory from "layers" dir to where the file(s)
                        passed with --inject-mcc should be copied to.
  --mbl-tools-version STRING
                        Specify the version of mbl-tools that this script comes
                        from. This is written to buildinfo.txt in the output
                        directory. By default, an attempt is made to obtain
                        this information automatically, but that is not always
                        possible.
  -o, --outputdir PATH  Specify a directory to store non-interactively built
                        artifacts. Note: Will not be updated by builds in
                        interactive mode.
  --root-passwd-file    The file containing the root user password in plain text.
  --tty                 Enable tty creation (default).
  --no-tty              Disable tty creation.
  -x                    Enable shell debugging in this script.
  --project STRING
                        The project to build. Default ${default_project}.

EOF
}

imagename="$default_imagename"
project="$default_project"
flag_tty="-t"

# Save the full command line for later - when we do a binary release we want a
# record of how this script was invoked
command_line="$(printf '%q ' "$0" "$@")"

args=$(getopt -o+ho:x -l boot-rot-key:,builddir:,project:,downloaddir:,external-manifest:,help,image-name:,inject-mcc:,kernel-rot-crt:,kernel-rot-key:,mcc-destdir:,mbl-tools-version:,outputdir:,root-passwd-file:,tty,no-tty -n "$(basename "$0")" -- "$@")
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
  --boot-rot-key)
    opt_prev=boot_rot_key
    ;;

  --builddir)
    opt_prev=builddir
    ;;

  --project)
    opt_prev=project
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

  --image-name)
    opt_prev=imagename
    ;;

  --inject-mcc)
    opt_append=inject_mcc_files
    ;;

  --kernel-rot-crt)
    opt_prev=kernel_rot_crt
    ;;

  --kernel-rot-key)
    opt_prev=kernel_rot_key
    ;;

  --mcc-destdir)
    opt_prev=mcc_destdir
    ;;

  --mbl-tools-version)
    opt_prev=mbl_tools_version
    ;;

  -o | --outputdir)
    opt_prev=outputdir
    ;;

  --root-passwd-file)
    opt_prev=root_passwd_file
    ;;

  --tty)
    flag_tty="-t"
    ;;

  --no-tty)
    flag_tty=
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

if [ -n "${builddir:-}" ]; then
  builddir=$(readlink -f "$builddir")
  if [ ! -d "$builddir" ]; then
    printf "missing builddir %s. Creating it.\n" "$builddir"
    mkdir -p "$builddir"
  fi
else
  printf "error: missing parameter --builddir PATH\n" >&2
  exit 3
fi

if [ -n "${outputdir:-}" ]; then
  outputdir=$(readlink -f "$outputdir")
  if [ ! -d "$outputdir" ]; then
    printf "missing outputdir %s. Creating it.\n" "$outputdir"
    mkdir -p "$outputdir"
  fi
fi

if [ -n "${downloaddir:-}" ]; then
  downloaddir=$(readlink -f "$downloaddir")
  if [ ! -d "$downloaddir" ]; then
    printf "missing downloaddir %s. Creating it.\n" "$downloaddir"
    mkdir -p "$downloaddir"
  fi
fi

if [ -n "${inject_mcc_files:-}" ]; then
  mkdir -p "$builddir/inject-mcc"
  for file in ${inject_mcc_files:-}; do
    base="$(basename "$file")"
    cp "$file" "$builddir/inject-mcc/$base"
    build_args="${build_args:-} --inject-mcc=$builddir/inject-mcc/$base"
  done
fi

if [ -n "${boot_rot_key:-}" ]; then
  mkdir -p "$builddir/inject-keys"
  cp "$boot_rot_key" "$builddir/inject-keys/rot_key.pem"
  build_args="${build_args:-} --inject-key=$builddir/inject-keys/rot_key.pem"
fi

if [ -n "${kernel_rot_crt:-}" ]; then
  mkdir -p "$builddir/inject-keys"
  cp "$kernel_rot_crt" "$builddir/inject-keys/mbl-fit-rot-key.crt"
  build_args="${build_args:-} --inject-key=$builddir/inject-keys/mbl-fit-rot-key.crt"
fi

if [ -n "${kernel_rot_key:-}" ]; then
  mkdir -p "$builddir/inject-keys"
  cp "$kernel_rot_key" "$builddir/inject-keys/mbl-fit-rot-key.key"
  build_args="${build_args:-} --inject-key=$builddir/inject-keys/mbl-fit-rot-key.key"
fi

if [ -n "${root_passwd_file:-}" ]; then
  base="$(basename "$root_passwd_file")"
  cp "$root_passwd_file" "$builddir/$base"
  build_args="${build_args:-} --root-passwd-file=$builddir/$base"
fi

build_script=$(build_script_for_project "$project")
dockerfile=$(dockerfile_for_project "$project")
if [ -n "${mcc_destdir:-}" ]; then
  build_args="${build_args:-} --mcc-destdir=$mcc_destdir"
fi

# If we didn't get an mbl-tools version on the command line, try to determine
# it using git. This isn't important in most cases and won't work in all
# environments so don't fail the build if it doesn't work.
if [ -z "${mbl_tools_version:-}" ]; then
  if which git &> /dev/null; then
    printf "Found git in path; attempting to determine mbl-tools version\n"
    if mbl_tools_version=$(git -C "$(dirname "$0")" rev-parse HEAD); then
      printf "Determined mbl-tools version to be %s\n" "$mbl_tools_version";
    else
      printf "Failed to determine mbl-tools version automatically; continuing anyway\n" >&2
      mbl_tools_version=""
    fi
  fi
fi

if [ -z "${SSH_AUTH_SOCK+false}" ]; then
  printf "error: ssh-agent not found.\n" >&2
  printf "To connect to Github please run an SSH agent and add your SSH key.\n" >&2
  printf "More info: https://help.github.com/articles/connecting-to-github-with-ssh/\n" >&2
  exit 4
fi

docker build -f "$execdir/$dockerfile" -t "$imagename" "$execdir"

if [ -n "${external_manifest:-}" ]; then
  name="$(basename "$external_manifest")"
  cp "$external_manifest" "$builddir/$name"
  set -- "--external-manifest=$builddir/$name" "$@"
fi

# The ${:+} expansion of download upsets shellcheck, but we do not
# want that instance quoted because that would inject an empty
# argument when download is not defined.
# shellcheck disable=SC2086
docker run --rm -i $flag_tty \
       --name "$default_containername" \
       -e LOCAL_UID="$(id -u)" -e LOCAL_GID="$(id -g)" \
       -e SSH_AUTH_SOCK="$SSH_AUTH_SOCK" \
       ${downloaddir:+-v "$downloaddir":"$downloaddir"} \
       ${outputdir:+-v "$outputdir":"$outputdir"} \
       -v "$(dirname "$SSH_AUTH_SOCK"):$(dirname "$SSH_AUTH_SOCK")" \
       -v "$builddir":"$builddir" \
       "$imagename" \
       ./${build_script} --builddir "$builddir" \
         ${build_args:-} \
         ${downloaddir:+--downloaddir "$downloaddir"} \
         ${outputdir:+--outputdir "$outputdir"} \
         --parent-command-line "$command_line" \
         ${mbl_tools_version:+--mbl-tools-version "$mbl_tools_version"} \
         "$@"
