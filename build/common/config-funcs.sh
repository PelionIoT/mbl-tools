# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# BASH functions that can be "source"d into a script to provide simple
# Config read/write and location of config directory


# Flag to record if we have read the config file, if so, don't save out the
# config. If we haven't read a file, we can create the initial one.
gbl_flag_config_save=


# Read arguments and values from a file
# Use a bash array for the arguments and values to preserve spaces in values
_config_read_args()
{
  # Config filename and path
  local config="$1"
  # Array variable reference to put the arguments into
  local -n config_args=$2
  if [ -r "$config" ]; then
    while read -r line; do
      # Need to split the arguments and values for the array
      local val=${line#-* }
      if [ "$val" == "$line" ]; then
        # No value, only an option
        config_args+=("$line")
      else
        local opt=${line% $val}
        config_args+=("$opt" "$val")
      fi
    done < "$config"
  fi
}

# Write arguments and values to a config file
# Outputs the arguments as argument and value on the same line
# NOTE: "--" must be last entry in list to end processing/output of the list
# NOTE: Does not output builddir as this is mandatory to find the config
_config_write_args()
{
  # Config filename and path
  local config="$1"
  shift
  if [ ! -e "$config" ] || [ -w "$config" ]; then
    rm -f "$config"
    local lastarg=""
    # Go through the other arguments (and values) saving them to a file
    # "--" is assumed to be the last arg in the list (which is not output)
    #  this forces the loop to output the "lastarg" before exiting
    while [ $# -gt 0 ]; do
      local arg="$1"
      shift
      if [ "$arg" == "" ]; then
        continue
      fi
      if [[ $arg = -* ]]; then
        # An argument, output any previous argument on its own
        if [ "$lastarg" != "" ]; then
            echo "$lastarg" >> "$config"
        fi
        lastarg=$arg
      else
        # A value - group arguments and values together

        # Special case - ignore the builddir as this is required
        # every invocation so shouldn't be stored
        if [[ ! $lastarg =~ --builddir ]]; then
            echo "$lastarg $arg" >> "$config"
        fi
        lastarg=""
      fi
      if [ "$arg" == "--" ]; then
        break
      fi
    done
  fi
}

# Called before parsing the arguments fully, check if the arguments
# only contain builddir, if so we can read the configs, else we write them
config_mode_check()
{
  local -n config_dir=$1
  shift
  # We need to read the builddir to locate the config file
  local args=$(getopt -q -o+ -l "builddir:" -- "$@")
  if [[ $args =~ --builddir ]]; then
    # Extract the last DIR from a possible list of "--builddir 'DIR'"
    local val=${args##*builddir \'}
    config_dir=${val%%\' --*}

    # Check if there are any other arguments on the command line
    # If not, then we can read the configs otherwise we should overwrite them
    val=${args##* --}
    if [ "$val" == "" ]; then
      gbl_flag_config_save=0
      return 1
    fi
  fi
  gbl_flag_config_save=1
  return 0
}

# Given config dir and filename, this will try and read args from that file
# The arguments are returned in a bash array in the given ref - config_args
# Global flag used to record whether a config was read, if not we can do
# a first write out of the config later
config_read()
{
  local config_dir="$1"
  local config_file="$2"
  local -n config_args=$3

  # Note: Pass given arg rather than our local ref to avoid circular ref
  _config_read_args "${config_dir}/${config_file}" $3
  if [ ${#config_args[@]} -gt 0 ]; then
    echo "Read configuration from ${config_dir}/${config_file}"
  fi
}

# Record the arguments in a referenced bash array for writing out later
# This should be called before parsing/shifting the arguments
config_save_args()
{
  local -n saved_args=$1
  shift
  saved_args=()
  while [ $# -gt 0 ]; do
    saved_args+=("$1")
    shift
  done
}

# Write out the saved arguments if there isn't already a config that was read
# Will only output arguments until it finds an "--" argument
config_write()
{
  local config_dir="$1"
  local config_file="$2"
  shift 2
  if [ $gbl_flag_config_save -eq 1 ]; then
    if [ -d "$config_dir" ]; then
      echo "Saving configuration to $config_dir/$config_file"
      _config_write_args "$config_dir/$config_file" "$@" "--"
    else
      echo "WARNING: Cannot write $config_file as $config_dir is not valid"
    fi
  fi
}
