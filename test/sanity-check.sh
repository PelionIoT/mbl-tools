#!/bin/bash

set -e
set -u
set -o pipefail

execdir="$(dirname "$0")"

rootdir="$(pwd)"
if [ $# -gt 0 ]; then
  rootdir="$1"
  shift
fi

rc=0

find "$rootdir" -name '*.sh' -print0 | xargs --no-run-if-empty -0 "$execdir/sanity_check.py" || rc=1
find "$rootdir" -name '*.sh' -print0 | xargs --no-run-if-empty -0 shellcheck --format=gcc  || rc=1

find "$rootdir" -name '*.py' -print0 | xargs --no-run-if-empty -0 pep8 || rc=1

exit "$rc"
