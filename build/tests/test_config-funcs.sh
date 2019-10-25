#!/bin/bash +e

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# Testing of the config functionality


execdir="$(readlink -e "$(dirname "$0")")"
srcdir="$execdir/../common"

source "$srcdir/config-funcs.sh"

validate_args()
{
  local -n list1=$1
  local -n list2=$2
  local invalid=0

  if [ ${#list1[@]} -ne ${#list2[@]} ]; then
    # Different lengths
    invalid=1
    echo "ERR: found different lengths of args"
  fi
  for i in "${!list1[@]}"; do
      if [ "${list1[$i]}" != "${list2[$i]}" ]; then
        echo "ERR: non-matching arg [${list1[$i]}] != [${list2[$i]}]"
        invalid=1
        break
      fi
  done
  set +e
  if [ $invalid -eq 1 ]; then
    echo "FAIL: [${list1[*]}] != [${list2[*]}]"
    return 1
  else
    echo "PASS"
    return 0
  fi
}

validate_output()
{
  local output=$1
  local expected=$2

  set +e
  if [ "$output" == "$expected" ]; then
    echo "PASS"
    return 0
  else
    echo "FAIL: Incorrect output [$output]"
    return 1
  fi
}

validate_files()
{
  local output=$1
  local expected=$2

  set +e
  diff "$1" "$2"
  if [ $? -ne 0 ]; then
    echo "FAIL: Differences found between $1 and $2"
    return 1
  fi
  return 0
}

validate_output_and_files()
{
  local output=$1
  local expected=$2
  local foutput=$3
  local fexpected=$4

  local err
  local ret=$(validate_output "$output" "$expected")
  if [ "$ret" == "PASS"  ]; then
    validate_files "$foutput" "$fexpected"
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
  local input=("--no" "matching" "--config" "options")
  local output=()
  local expected=("--no" "matching" "--config" "options" "--")
  config_setup output "${input[@]}"
  validate_args output expected
  return $?
}

test_opts2()
{
  echo "Test: load-config and save-config with same file"
  local input=("--load-config" "same.cfg" "--save-config" "same.cfg")
  local output=$(config_setup output "${input[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_opts3()
{
  echo "Test: load and save (shortened) with same file "
  local input=("--load" "same.cfg" "--save" "same.cfg")
  local output=$(config_setup output "${input[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_opts4()
{
  echo "Test: load-config= and save= (equals style) with same file "
  local input=("--load-config=same.cfg" "--save=same.cfg")
  local output=$(config_setup output "${input[@]}")
  local expected="ERROR: Unsupported loading and saving to same config file - same.cfg"
  validate_output "$output" "$expected"
}

test_load1()
{
  echo "Test: load-config with invalid file"
  local input=("--load-config" "invalid.cfg")
  local output=$(config_setup output "${input[@]}")
  local expected="ERROR: Unreadable configuration file invalid.cfg"
  validate_output "$output" "$expected"
  return $?
}

TEST2=("--some" "option" "--equals=with spaces" "--another" "--" "--extra" "args with spaces" "--yes")

test_load2()
{
  echo "Test: load-config with valid file"
  local input=("--load-config" "tcf_load2.cfg")
  local output=()
  local -n expected=TEST2
  config_setup output "${input[@]}"
  validate_args output expected
  return $?
}

test_save1()
{
  echo "Test: save-config with invalid file"
  local input=("--save-config" ".")
  local output=$(config_setup output "${input[@]}")
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
  local -n input=TEST2
  local output=$(config_setup cfg "${input[@]}" "--save-config" "$fileout")
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
  local input=("--save-config" "$fileout" "--new" "test opt" "--maybe" "--" "--load-config" "$filecfg" "--wildcard" "****")
  local output=$(config_setup cfg "${input[@]}")
  local expected=$(echo -en "Read configuration from $filecfg\nSaving configuration to $fileout")
  validate_output_and_files "$output" "$expected" "$fileout" "$fileexpected"
  return $?
}

# main
FAILED=0

test_opts1
FAILED=$(($FAILED + $?))
test_opts2
FAILED=$(($FAILED + $?))
test_opts3
FAILED=$(($FAILED + $?))
test_opts4
FAILED=$(($FAILED + $?))
test_load1
FAILED=$(($FAILED + $?))
test_load2
FAILED=$(($FAILED + $?))
test_save1
FAILED=$(($FAILED + $?))
test_save2
FAILED=$(($FAILED + $?))
test_load_save1
FAILED=$(($FAILED + $?))

echo "FAILURES: $FAILED"
return $FAILED
