#!/bin/bash

set -e
set -u
set -o pipefail

usage()
{
  cat <<EOF

usage: build-optee.sh [OPTION] [WORKDIR]

  --builddir DIR	Use DIR for build, default CWD.
  --[no-]clean		Clean any existing build.
  -h, --help		Print brief usage information and exit.
  --target TARGET	Build for TARGET.
			  rpi3
  -x			Enable shell debugging in this script.

EOF
}

target=rpi3

args=$(getopt -o+hx -l builddir:,clean,no-clean,help,target: -n $(basename "$0") -- "$@")
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
  --builddir)
    opt_prev=builddir
    ;;

  --clean)
    flag_clean=1
    ;;

  --no-clean)
    flag_clean=0
    ;;

  -h | --help)
    usage
    exit 0
    ;;

  --target)
    opt_prev=target
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

if [ -z "${builddir:-}" ]; then
  builddir=$(pwd)
fi
builddir=$(pwd)

case $target in
    rpi3)
	;;
    *)
	printf "error: unrecognized --target $target\n" >&2
	exit 3
	;;
esac

if [ ${flag_clean:-0} -eq 1 ]; then
    rm -rf "$builddir"
fi

mkdir -p "$builddir"
cd "$builddir"

if [ ! -e .ss-sync ]; then
  repo init -u https://github.com/OP-TEE/manifest.git -m ${target}.xml # [-b ${BRANCH}]
  repo sync
  touch .ss-sync
fi

cd build

make -j 8 toolchains
make -j 8 all
# There is no run target for RPi3
# make -j 8 run
