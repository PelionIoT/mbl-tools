#!/bin/bash

set -e
set -u
set -o pipefail

execdir="$(dirname "$0")"
execdir="$(cd "$execdir"; pwd)"

tmpdir="$(mktemp -d)"

cleanup()
{
  rm -rf "$tmpdir"
}

trap cleanup 0

usage()
{
  cat <<EOF

usage: mbl-rebase.sh [OPTION] URL BRANCH ONTO

  --builddir DIR        Use DIR for build, default CWD.
  -h, --help            Print brief usage information and exit.
  -x                    Enable shell debugging in this script.

Rebase branch BRANCH in git repository URL onto branch ONTO.

EOF
}

rebase()
{
  local url="$1"
  local branch="$2"
  local onto="$3"
  local stamp
  local repodir
  local tag

  repodir="$builddir/repo"

  stamp="$(date +"%Y%m%d-%H%M%S")"
  tag="$branch-$stamp"


  if true; then
    rm -rf "$repodir"
    git clone -q "$url" "$repodir"
  fi

  new_base="$(git -C "$repodir" merge-base "origin/$branch" "origin/$onto")"
  old_base="$(git -C "$repodir" rev-parse "origin/$onto")"

  if [ "$new_base" == "$old_base" ]; then
    printf "info: rebase %s not necessary\n" "$branch"
    return 0
  fi

  existing="$(git -C "$repodir" tag -l "$tag")"
  if [ -n "$existing" ]; then
    printf "error: tag %s already exists\n" "$tag" >&2
    return 1
  fi

  git -C "$repodir" tag "$tag" "origin/$branch"
  git -C "$repodir" checkout -q -b "$branch" "origin/$branch"
  git -C "$repodir" rebase -q "origin/$onto"
  git -C "$repodir" push -q origin --tags
  git -C "$repodir" push -q -f origin "$branch"
}

args=$(getopt -ohj:l:x -l builddir: -n "$(basename "$0")" -- "$@")
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

  -h | --help)
    usage
    exit 0
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
  builddir="$tmpdir"    
fi

if [ $# -ne 3 ]; then
  printf "error: expected 3 arguments\n" >&2
  exit 3
fi

url="$1"; shift
branch="$1"; shift
onto="$1"; shift

rebase "$url" "$branch" "$onto"
