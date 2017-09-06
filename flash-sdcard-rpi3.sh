#!/bin/bash

# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

set -e
set -u
set -o pipefail

tmpdir=$(mktemp -d)

cleanup()
{
  rm -rf "$tmpdir"
}

trap cleanup 0

usage()
{
  cat <<EOF

usage: flash-sdcard-rpi3.sh [OPTION]...

  -h, --help		Print brief usage information and exit.
  --device DEVICE	SDCARD Device
EOF
}

args=$(getopt -o+hx -l device:,help -n $(basename "$0") -- "$@")
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
  -h | --help)
    usage
    exit 0
    ;;

  --device)
    opt_prev=device
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

if [ -z "${device:-}" ]; then
    printf "error: missing --device=DEVICE\n" >&2
    exit 3
fi

# dev="/dev/sdd"

# Unmount any partitions on the device that have already been mounted.
for path in $(mount | grep "$device" | cut -f1 -d" ")
do
    umount "$path"
done

cat <<EOF
fdisk /dev/sdx   # where sdx is the name of your sd-card
> p             # prints partition table
> d             # repeat until all partitions are deleted
> n             # create a new partition
> p             # create primary
> 1             # make it the first partition
> <enter>       # use the default sector
> +32M          # create a boot partition with 32MB of space
> n             # create rootfs partition
> p
> 2
> <enter>
> <enter>       # fill the remaining disk, adjust size to fit your needs
> t             # change partition type
> 1             # select first partition
> e             # use type 'e' (FAT16)
> a             # make partition bootable
> 1             # select first partition
> p             # double check everything looks right
> w             # write partition table to disk.
EOF

path="$tmpdir/boot"

mkfs.vfat -F16 -n BOOT "$device"1
mkdir -p "$path"
mount "$device"1 "$path"
cd "$path/.."
gunzip -cd /home/marcus/work/mbed-linux/optee/optee/build/../gen_rootfs/filesystem.cpio.gz | sudo cpio -idmv "boot/*"
umount "$path"
rm -d "$path"

path="$tmpdir/rootfs"
mkfs.ext4 -F -q -L rootfs "$device"2
mkdir -p "$path"
mount "$device"2 "$path"
cd "$path"
gunzip -cd /home/marcus/work/mbed-linux/optee/optee/build/../gen_rootfs/filesystem.cpio.gz | sudo cpio -idmv
rm -rf "$path/boot/"*
cd ..
umount "$path"
