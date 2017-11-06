#!/bin/bash

set -e
set -u
set -o pipefail

execdir="$(dirname "$0")"
execdir="$(cd "$execdir"; pwd)"

testdir="$(pwd)/testit"

rm -rf "$testdir"
mkdir -p "$testdir"

repodir="$testdir/repo"
mkdir -p "$repodir"

git -C "$repodir" init
touch "$repodir/README"
git -C "$repodir" add README
git -C "$repodir" commit -m "First commit"
git -C "$repodir" checkout -q -b release master
touch "$repodir/foo.c"
git -C "$repodir" add foo.c
git -C "$repodir" commit -m "Adding foo.c"
git -C "$repodir" checkout -q master
echo "a" >> "$repodir/README"
git -C "$repodir" add README
git -C "$repodir" commit -q -m "Second commit"

"$execdir/mbl-rebase.sh" --builddir "$testdir/workspace" "$repodir" release master
