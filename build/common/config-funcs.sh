#!/bin/bash

# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# BASH functions that can be "source"d into a script to provide simple
# config functionality that supports command line options:
#   --save-config FILE      - save all the arguments into FILE and exit
#   --load-config FILE      - load arguments from FILE and combine them
#                             with the command line arguments
#
# Example usage to replace command line args ($@) with extra args from config:
#   source config-funcs.sh
#   config=()
#   config_setup config "$@"
#   eval set -- "${config[@]}"
#
# Notes:
# * only supports options without values or options with a single value
# * supports "--" option that splits primary and secondary arguments
# * SC2178: Arrays passed around by reference confuses shellcheck
#           https://github.com/koalaman/shellcheck/issues/1225
# * SC2034: Arrays passed around by reference confuses shellcheck
#           https://github.com/koalaman/shellcheck/issues/1543


# Read arguments and values from a file
# Split them into primary and secondary based on "--" in the file
# Return bash arrays for the arguments and values to preserve spaces in values
# Params: NAME ARRAY_REF ARRAY_REF
_config_read_args()
{
  # Config filename and path
  local config="$1"
  # Array variable reference to put the arguments into
  local -n config_primary=$2
  local -n config_secondary=$3
  local stage=1
  if [ -r "$config" ]; then
    while read -r line; do
      if [[ "$line" =~ ^--\ *$ ]]; then
        # Switch to secondary stage on "--"
        stage=2
        continue  # Skip the "--"
      fi
      local val
      pat="^-[-a-z]+="
      if [[ "$line" =~ $pat ]]; then
        # Catch --option=value and don't split it
        val="$line"
      else
        # Split the arguments and values for the array
        val=${line#-* } # Remove the argument part
      fi
      if [ "$val" == "$line" ]; then
        # No value, only an option (or option=value)
        if [ $stage -eq 1 ]; then
          config_primary+=("$line")
        else
          config_secondary+=("$line")
        fi
      else
        local opt=${line% $val}
        if [ $stage -eq 1 ]; then
          config_primary+=("$opt" "$val")
        else
          config_secondary+=("$opt" "$val")
        fi
      fi
    done < "$config"
  fi
}

# Write arguments and values to a config file
# Outputs the arguments as argument and value on the same line
# NOTE: "--END--" must be last entry in list to end processing/output of the list
# Params: NAME ARGS_LIST... --END--
_config_write_args()
{
  # Config filename and path
  local config="$1"
  shift
  if [ ! -e "$config" ] || [[ -w "$config" && -f "$config" ]]; then
    # Create empty file
    rm -f "$config"
    touch "$config"
    local lastarg=""
    # Go through the other arguments (and values) saving them to a file
    # "--END--" is assumed to be the last arg in the list (which is not output)
    #  this forces the loop to output the "lastarg" before exiting
    while [ $# -gt 0 ]; do
      local arg="$1"
      shift
      if [ -z "$arg" ]; then
        # Ignore empty arguments
        continue
      fi
      if [[ "$arg" =~ ^- ]]; then
        # An argument, output any previous argument on its own
        if [ -n "$lastarg" ]; then
          echo "$lastarg" >> "$config"
        fi
        lastarg=$arg
      else
        # A value - group arguments and values together
        if [ -n "$lastarg" ]; then
          echo "$lastarg $arg" >> "$config"
        else
          echo "$arg" >> "$config"
        fi
        lastarg=""
      fi
      if [ "$arg" == "--END--" ]; then
        break
      fi
    done
  fi
}

# Given a config, this will try and read args from that file
# The arguments are split by "--" returned in bash arrays in the given refs
# Params: NAME ARRAY_REF ARRAY_REF
_config_read()
{
  local config="$1"
  # shellcheck disable=SC2178
  local -n config_primary=$2
  # shellcheck disable=SC2178
  local -n config_secondary=$3

  if [ -r "${config}" ]; then
    _config_read_args "${config}" "${!config_primary}" "${!config_secondary}"
    if [ ${#config_primary[@]} -gt 0 ] || [ ${#config_secondary[@]} -gt 0 ]; then
      echo "Read configuration from ${config}"
    fi
  else
    echo "ERROR: Unreadable configuration file ${config}"
    return 1
  fi
}

# Write out the arguments to the given file
# Params: NAME ARGS_LIST...
_config_write()
{
  local config_file="$1"
  shift
  if [ -d "$(dirname "$config_file")" ]; then
    if [ ! -e "$config_file" ] || [[ -w "$config_file" && -f "$config_file" ]]; then
      echo "Saving configuration to $config_file"
      _config_write_args "$config_file" "$@" "--END--"
    else
      echo "ERROR: Cannot write $config_file as invalid file"
    fi
  else
    echo "ERROR: Cannot write $config_file as directory is invalid"
    return 1
  fi
}

# Read through the arguments for the given config option (without --) so we can
# remove the option and return the option value - filename
# Needs a reference to store the filename and the updated args list, and then
# the full list of args to parse
# option
# NOTE: "--END--" must be last entry in list to end processing/output of the list
# Params: NAME NAME_REF ARRAY_REF ARGS_LIST... --END--
_config_get_filename()
{
  # We need to read the option to get the filename
  local optname=$1
  local -n ret_filename=$2
  local -n ret_args=$3
  shift 3
  ret_args=()

  # Go through each option/value looking for the option we want, and remove it
  local lastarg=""
  local optreturn=""
  while [ $# -gt 0 ]; do
    local arg="$1"
    shift
    if [ -z "$arg" ]; then
      # Ignore empty arguments
      continue
    fi
    local optcheck
    if [[ "$arg" =~ ^- ]]; then
      # An argument, check if the lastarg is the option we want
      # (it will be in the form --option=value)
      if [ -n "$lastarg" ]; then
        set +e
        optcheck=$(getopt -q -o+ -l "$optname:" -- "$lastarg")
        set -e
        # getopt returns " --" if its not the option we want
        if [ "$optcheck" == " --" ]; then
          ret_args+=("$lastarg")
        else
          # Save the output from getopt for later
          optreturn="$optcheck"
        fi
      fi
      # Save the argument to look at later with a possibly value
      lastarg=$arg
    else
      # A value - check using the last argument and this value for the option
      # (form of --option value)
      set +e
      optcheck=$(getopt -q -o+ -l "$optname:" -- "$lastarg" "$arg")
      set -e
      # getopt returns " -- '$arg'" if its not found as it removes unknown opts
      if [[ "$optcheck" =~ ^\ --\  ]]; then
          if [ -n "$lastarg" ]; then
            ret_args+=("$lastarg")
          fi
          ret_args+=("$arg")
      else
        # Save the output from getopt for later
        optreturn="$optcheck"
      fi
      lastarg=""
    fi
    if [ "$arg" == "--END--" ]; then
      break
    fi
  done
  ret_filename=""
  if [ -n "$optreturn" ]; then
    # Extract the file from the last found "--option 'FILE' --"
    ret_filename=${optreturn##*$optname \'}
    ret_filename=${ret_filename%%\' --*}
  fi
}

# Combine the command line (cl) arguments with the config arguments, such that:
# [primary config] [cl args (before --)] -- [secondary args] [cl args (after --)]
# Params: ARRAY_REF ARRAY_REF ARRAY_REF ARGS_LIST...
_config_combine_args()
{
  # shellcheck disable=SC2178
  local -n ret_args=$1
  # shellcheck disable=SC2178
  local -n config_primary=$2
  # shellcheck disable=SC2178
  local -n config_secondary=$3
  shift 3
  ret_args=()

  # Put the primary config args first
  local arg
  set +u # Ignore if the config_primary array is empty
  for arg in "${config_primary[@]}"; do
    ret_args+=("$arg")
  done
  set -u
  # Next add all the command line arguments upto "--"
  while [ $# -gt 0 ]; do
    arg="$1"
    shift
    if [[ "$arg" =~ ^--\ *$ ]]; then
      # Found "--" exit the loop without recording it as we may get arguments
      # that don't contain "--"
      break
    fi
    ret_args+=("$arg")
  done
  # Add the delimiter between args (in case it wasn't in the command line)
  ret_args+=("--")
  # Now add the secondary config args
  set +u # Ignore if the config_secondary array is empty
  for arg in "${config_secondary[@]}"; do
    ret_args+=("$arg")
  done
  set -u
  # Lastly add any remaining args
  while [ $# -gt 0 ]; do
    ret_args+=("$1")
    shift
  done
}

# Single quote all arguments
# Needed for the eval operation (eval set -- "${config[@]}") that will be
# perfomed on the config after we return
# Params: ARRAY_REF ARGS_LIST...
_config_add_quotes()
{
  # shellcheck disable=SC2178
  local -n ret_args=$1
  shift 1
  ret_args=()

  while [ $# -gt 0 ]; do
    if [ "$1" != "--" ]; then
      ret_args+=("'$1'")
    else
      ret_args+=("$1")
    fi
    shift
  done
}

# Single config read/write function
# First parameter is used on read and is an array populated with the combined
# command line and config arguments
# Rest of parameters are the command line args passed via "$@"
# On write, command line args are written to file and then exit
# Params: ARRAY_REF ARGS_LIST...
config_setup()
{
  local -n config_args=$1
  shift

  # Avoid circular references by unique naming of arrays
  local __args=()
  # shellcheck disable=SC2034
  local __config_primary=()
  # shellcheck disable=SC2034
  local __config_secondary=()

  local config_load=""
  _config_get_filename "load-config" config_load __args "$@" "--END--"
  local config_save=""
  set +u  # __args could be empty, so allow unbound vars
  _config_get_filename "save-config" config_save __args "${__args[@]}" "--END--"
  set -u

  if [ -n "$config_load" ] || [ -n "$config_save" ]; then
    if [ "$config_save" == "$config_load" ]; then
      echo "ERROR: Unsupported loading and saving to same config file - $config_save"
      exit 2
    fi
  fi

  # Support loading from one config and saving to another
  if [ -n "$config_load" ]; then
    _config_read "$config_load" __config_primary __config_secondary
  fi
  set +u  # __args could be empty, so allow unbound vars
  _config_combine_args "${!config_args}" __config_primary __config_secondary "${__args[@]}"
  set -u
  if [ -n "$config_save" ]; then
    set +u  # __args could be empty, so allow unbound vars
    _config_write "$config_save" "${config_args[@]}"
    set -u
    exit 0
  fi
  _config_add_quotes "${!config_args}" "${config_args[@]}"
}
