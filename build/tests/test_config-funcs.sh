#!/bin/bash +e

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# Testing of the config functionality

# Notes:
# * SC2178: Arrays passed around by reference confuses shellcheck
# * SC2034: Arrays passed around by reference confuses shellcheck


execdir="$(readlink -e "$(dirname "$0")")"
srcdir="$execdir/../common"

# shellcheck disable=SC1090
source "$srcdir/config-funcs.sh"

validate_args()
{
  local -n lout=$1
  local -n lexp=$2
  local invalid=0

  if [ ${#lout[@]} -ne ${#lexp[@]} ]; then
    # Different lengths
    invalid=1
    echo "ERR: found different lengths of args"
  fi
  for i in "${!lout[@]}"; do
    # Special case where -- is not quoted
    if [ "${lexp[$i]}" == "--" ]; then
      if [ "${lout[$i]}" == "--" ]; then
        continue
      else
        echo "ERR: non-matching arg [${lout[$i]}] != [${lexp[$i]}]"
        invalid=1
        break
      fi
    fi
    # Otherwise the output will be wrapped in '' & the expected list won't be!
    if [ "${lout[$i]}" != "'${lexp[$i]}'" ]; then
      echo "ERR: non-matching arg [${lout[$i]}] != ['${lexp[$i]}']"
      invalid=1
      break
    fi
  done
  set +e
  if [ $invalid -eq 1 ]; then
    echo "FAIL: [${lout[*]}] != [${lexp[*]}]"
    echo " (note: expected args are NOT wrapped in single quotes)"
    return 1
  else
    echo "PASS"
    return 0
  fi
}

validate_output()
{
  local out=$1
  local exp=$2

  set +e
  if [ "$out" == "$exp" ]; then
    echo "PASS"
    return 0
  else
    echo "FAIL: Incorrect output [$out]"
    return 1
  fi
}

validate_files()
{
  local out=$1
  local exp=$2

  set +e
  diff "$out" "$exp"
  ret=$?
  if [ $ret -ne 0 ]; then
    echo "FAIL: Differences found between $out and $exp"
    return 1
  fi
  echo "PASS"
  return 0
}

validate_output_and_files()
{
  local out=$1
  local exp=$2
  local fout=$3
  local fexp=$4

  local ret
  ret=$(validate_output "$out" "$exp")
  if [ "$ret" == "PASS"  ]; then
    validate_files "$fout" "$fexp"
    return $?
  else
    echo "$ret"
    return 1
  fi
}

remove_save_file()
{
  local file=$1
  if [ -e "$file" ]; then
    set -e
    rm "$file"
    set +e
  fi
}

# Tests

test_opts1()
{
  echo "Test: No config options"
  local ainput=("--no" "matching" "--config" "options")
  local aoutput=()
  local aexpected=("--no" "matching" "--config" "options" "--")
  config_setup aoutput "${ainput[@]}"
  validate_args aoutput aexpected
  return $?
}

test_opts2()
{
  echo "Test: load-config and save-config with same file"
  local ainput=("--load-config" "same.cfg" "--save-config" "same.cfg")
  local output
  output=$(config_setup output "${ainput[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_opts3()
{
  echo "Test: load and save (shortened) with same file "
  local ainput=("--load" "same.cfg" "--save" "same.cfg")
  local output
  output=$(config_setup output "${ainput[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_opts4()
{
  echo "Test: load-config= and save= (equals style) with same file "
  local ainput=("--load-config=same.cfg" "--save=same.cfg")
  local output
  output=$(config_setup output "${ainput[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_load1()
{
  echo "Test: load-config with invalid file"
  local ainput=("--load-config" "invalid.cfg")
  local output
  output=$(config_setup output "${ainput[@]}")
  local expected="ERROR: Unreadable configuration file invalid.cfg"
  validate_output "$output" "$expected"
  return $?
}

# shellcheck disable=SC2034
TEST2=("--some" "option" "--equals=with spaces" "--another" "--" "--extra" "args with spaces" "--yes")

test_load2()
{
  echo "Test: load-config with valid file"
  local ainput=("--load-config" "tcf_load2.cfg")
  # shellcheck disable=SC2034
  local aoutput=()
  # shellcheck disable=SC2034 disable=SC2178
  local -n aexpected=TEST2
  config_setup aoutput "${ainput[@]}"
  validate_args aoutput aexpected
  return $?
}

test_save1()
{
  echo "Test: save-config with invalid file"
  local ainput=("--save-config" ".")
  local output
  output=$(config_setup cfg "${ainput[@]}")
  local expected="ERROR: Cannot write . as invalid file"
  validate_output "$output" "$expected"
  return $?
}

test_save2()
{
  echo "Test: save-config with valid file"
  local fileout="tcf_save2.cfg"
  remove_save_file "$fileout"
  local fileexpected="tcf_load2.cfg"
  # shellcheck disable=SC2178
  local -n ainput=TEST2
  local output
  output=$(config_setup cfg "${ainput[@]}" "--save-config" "$fileout")
  local expected="Saving configuration to $fileout"
  validate_output_and_files "$output" "$expected" "$fileout" "$fileexpected"
  return $?
}

test_load_save1()
{
  echo "Test: load-config and save-config with valid files"
  local filecfg="tcf_load2.cfg"
  local fileout="tcf_ls_save1.cfg"
  remove_save_file "$fileout"
  local fileexpected="tcf_ls_load1.cfg"
  local ainput=("--save-config" "$fileout" "--new" "test opt" "--maybe" "--" "--load-config" "$filecfg" "--wildcard" "****")
  local output
  output=$(config_setup cfg "${ainput[@]}")
  local expected
  expected=$(echo -en "Read configuration from $filecfg\nSaving configuration to $fileout")
  validate_output_and_files "$output" "$expected" "$fileout" "$fileexpected"
  return $?
}

# main
FAILED=0

test_opts1
FAILED=$((FAILED + $?))
test_opts2
FAILED=$((FAILED + $?))
test_opts3
FAILED=$((FAILED + $?))
test_opts4
FAILED=$((FAILED + $?))
test_load1
FAILED=$((FAILED + $?))
test_load2
FAILED=$((FAILED + $?))
test_save1
FAILED=$((FAILED + $?))
test_save2
FAILED=$((FAILED + $?))
test_load_save1
FAILED=$((FAILED + $?))

echo "FAILURES: $FAILED"
exit $FAILED
