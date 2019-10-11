# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# BASH functions that can be "source"d into a script to provide simple
# config functionality that supports command line options:
#   --save-config FILE      - save all the arguments into FILE and exit
#   --config FILE           - load arguments from FILE and combine them
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


# Read arguments and values from a file
# Split them into primary and secondary based on "--" in the file
# Return bash arrays for the arguments and values to preserve spaces in values
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
      if [[ "$line" =~ ^\ *--\ *$ ]]; then
        # Switch stages on "--"
        stage=2
        continue
      fi
      # Need to split the arguments and values for the array
      local val=${line#-* }
      if [ "$val" == "$line" ]; then
        # No value, only an option
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
# NOTE: Strips out --config and --save-config options
_config_write_args()
{
  # Config filename and path
  local config="$1"
  shift
  if [ ! -e "$config" ] || [ -w "$config" ]; then
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
      if [[ $arg = -* ]]; then
        # An argument, output any previous argument on its own
        if [ "$lastarg" != "" ]; then
          echo "$lastarg" >> "$config"
        fi
        lastarg=$arg
      else
        # A value - group arguments and values together

        # Ignore the --config or --save-config as this specifies this config!
        if [[ ! $lastarg =~ --config ]] && [[ ! $lastarg =~ --save-config ]]; then
            echo "$lastarg $arg" >> "$config"
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
# The arguments are returned in a bash array in the given ref - config_args
# Global flag used to record whether a config was read, if not we can do
# a first write out of the config later
_config_read()
{
  local config="$1"
  local -n config_primary=$2
  local -n config_secondary=$3

  if [ -r ${config} ]; then
    _config_read_args "${config}" ${!config_primary} ${!config_secondary}
    if [ ${#config_primary[@]} -gt 0 ] || [ ${#config_secondary[@]} -gt 0 ]; then
      echo "Read configuration from ${config}"
    fi
  else
    echo "ERROR: Unreadable configuration file ${config}"
    return 1
  fi
}

# Write out the arguments
_config_write()
{
  local config_file="$1"
  shift
  if [ -d "$(dirname $config_file)" ]; then
    echo "Saving configuration to $config_file"
    _config_write_args "$config_file" "$@" "--END--"
  else
    echo "ERROR: Cannot write $config_file as directory is invalid"
    return 1
  fi
}

# Called before parsing the arguments fully, skim the arguments for the
# config options so we can read the config file early - returns option value
_config_get_filename()
{
  # We need to read the option to get the filename
  local optname=$1
  shift
  local args=$(getopt -q -o+ -l "$optname:" -- "$@")
  local filename=""
  if [[ $args =~ --$optname ]]; then
    # Extract the last file from a possible list of "--config 'FILE' --"
    filename=${args##*$optname \'}
    filename=${filename%%\' --*}
  fi
  printf "$filename"
}

# Combine the command line (cl) arguments with the config arguments, such that:
# primary config & cl args (before --) -- secondary args & cl args (after --)
# Strips out "--config" option and value as not needed anymore
_config_combine_args()
{
  local -n ret_args=$1
  local -n config_primary=$2
  local -n config_secondary=$3
  shift 3
  ret_args=()
  # Put the primary config args first
  local arg
  local lastarg=""
  set +u # Ignore if the config_primary array is empty
  for arg in "${config_primary[@]}"; do
    ret_args+=($arg)
  done
  set -u
  # Next add all the command line arguments upto "--"
  while [ $# -gt 0 ]; do
    arg=$1
    if [[ "$arg" =~ ^\ *--\ *$ ]]; then
      shift
      break
    else
      # Remove the -config argument and its value
      if [[ ! "$arg" =~ --config ]] && [[ ! "$lastarg" =~ --config ]]; then
        ret_args+=($arg)
      fi
      lastarg=$arg
      shift
    fi
  done
  # Add the delimiter between args (in case it wasn't in the command line)
  ret_args+=("--")
  # Now add the secondary config args
  set +u # Ignore if the config_secondary array is empty
  for arg in "${config_secondary[@]}"; do
    ret_args+=($arg)
  done
  set -u
  # Lastly add any remaining args
  while [ $# -gt 0 ]; do
    ret_args+=($1)
    shift
  done
}

# Single config read/write function
# First parameter is used on read and is an array populated with the combined
# command line and config arguments
# Rest of parameters are the command line args passed via "$@"
# On write, command line args are written to file and then exit
config_setup()
{
  local -n config_args=$1
  shift
  local config_load=$(_config_get_filename "config" "$@")
  local config_save=$(_config_get_filename "save-config" "$@")

  # Avoid circular references by unique naming
  local __config_primary=()
  local __config_secondary=()
  if [ "$config_save" != "" ]; then
    _config_write "$config_save" "$@"
    exit 0
  elif [ "$config_load" != "" ]; then
    _config_read "$config_load" __config_primary __config_secondary
  fi
  _config_combine_args ${!config_args} __config_primary __config_secondary "$@"
}
