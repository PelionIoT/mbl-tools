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

# Collect all shell files
SHELL_FILES=$(find "$rootdir" -type f | while read -r in; do if file -i "${in}" | grep -q text/x-shellscript; then echo "${in}" ; fi ; done)

# Custom script to check tabs existence in shell scripts
printf "Running tab_finder.py on shell files...\n"
echo "$SHELL_FILES" | xargs --no-run-if-empty "$execdir/tab_finder.py" || rc=1

# Run shellcheck on bash files
printf "Running shellcheck on shell files...\n"
echo "$SHELL_FILES" | xargs --no-run-if-empty shellcheck --format=gcc  || rc=1

# Collect all Python files
PYTHON_FILES=$(find "$rootdir" -type f | while read -r in; do if file -i "${in}" | grep -q x-python; then echo "${in}" ; fi ; done)

# Run black on python files - https://black.readthedocs.io/en/stable/
printf "Running black on python files...\n"
echo "$PYTHON_FILES" | xargs --no-run-if-empty black -v --check --diff || rc=1

# Run pycodestyle on python files
printf "Running pycodestyle on python files...\n"
echo "$PYTHON_FILES" | xargs --no-run-if-empty pycodestyle || rc=1

# Run pep257 on python files
printf "Running pep257 on python files...\n"
echo "$PYTHON_FILES" | xargs --no-run-if-empty pep257 || rc=1

exit "$rc"
