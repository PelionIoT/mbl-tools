<!--Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.-->
# mbl-licensing-checker - Mbed Linux OS repositories licensing checker

`mbl-licensing-checker` is a static analysis tool for checking compliance with licensing and copyrights within Mbed Linux OS repositories.

## Installation and usage

### Installation

`mbl-licensing-checker` can be installed by running:
```
pip install .
```

## Usage

```
usage: mbl-licensing-checker [arguments] [<file|dir>...]

MBL repo licensing checker application

positional arguments:
  [<file|dir>...]       List of path to file and/or directory to check for
                        licensing. (default: .)

```


## Return code

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 0    | Success - no licenses violation                   |
| 1    | Some licenses violations were found               |
| 2    | Incorrect usage of the application - see error    |

## Command line options

```
optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -e [EXPLAIN], --explain [EXPLAIN]
                        Show explanation of each error (default: None)
  -d [DEBUG], --debug [DEBUG]
                        Print debug information (default: None)
  -v [VERBOSE], --verbose [VERBOSE]
                        Print application status information (default: None)
  --count [COUNT]       Print total number of errors to stdout (default: None)
  --config <path>       Search and use configuration starting from this
                        directory (default: None)
  --match <pattern>     Check only files that exactly match <pattern> regular
                        expression; default is --match='.*\.(bb|bbappend|bbcla
                        ss|c|cpp|h|hpp|inc|py|sh)$' which matches files that
                        don't start with 'test_' but end with the file
                        extensions in <pattern> (default: None)
  --match-dir <pattern>
                        Search only dirs that exactly match <pattern> regular
                        expression; default is --match-dir='[^\.].*', which
                        matches all dirs that don't start with a dot (default:
                        None)

Note:
  When using --match, or --match-dir consider whether you should use a
  single quote (') or a double quote ("), depending on your OS, Shell, etc.

Error Check Arguments:
  Select the list of error codes to check for. If not specified, default to
  `--convention=reuse_v2_0`.If you wish to change a list of error to check
  (for example, if you selected a known convention but wish to ignore a
  specific error from it or add a new one) you can use
  `--add-[ignore/select]` in order to do so.

  --convention <name>   Choose the basic list of checked errors by specifying
                        an existing convention. Possible conventions: none,
                        reuse_v2_0. (default: None)
  --add-select <codes>  Add extra error codes to check to the basic list of
                        errors previously set --convention. (default: None)
  --add-ignore <codes>  Ignore extra error codes by removing them from the
                        basic list previously set by --convention. (default:
                        None)
```

## Configuration files

`mbl-licensing-checker` supports ini-like configuration files. In order for `mbl-licensing-checker` to use it, it must be named `.mbl-licensing-checker`, and have a `[mbl-licensing-checker]` section.

The search for configuration file start at the path specified with the `--config` options. The search for configuration file carries on up the directory tree until one is found.

The configuration file can specify:
* the license convention to use (e.g REUSE version 2.0)
* additional error codes to check in addition to a chosen list or convention
* error codes to ignore from a chosen list or convention
* regular expression for files to include in the check
* regular expression for directories to include in the check

When a configuration file is found, `mbl-licensing-checker` inherits the configuration from one found in a parent directory and merge them. Set the `inherit` argument to `False` in the configuration file of the child directory to prevent configuration inheritance.

The merge process is as follows:

* If the `convention` is specified in the child configuration, override the parent's and set the new error codes to check.
* If `add-ignore` or `add-select` were specified, remove/add the specified error codes from the checked error codes list.
* If `match` or `match-dir` were specified override the parent's.


### Example

```
[mbl-licensing-checker]
inherit = false
convention = reuse_v2_0
add-ignore = D100,D300
match = .*\.py
```

## Error codes

### Grouping

| Missing copyright notice                                                       ||
|--------------------------|------------------------------------------------------|
| D100                     | Missing ARM copyright notice                         |
| D101                     | Missing the fully qualified path and filename        |
| D102                     | Missing the URI to the source code repository        |
| D103                     | Missing a copy of the original copyright notice      |

| Missing licence information                                                    ||
|--------------------------|:-----------------------------------------------------|
| D200                     | Missing the SPDX license Identifier                  |

| License Information issues                                                     ||
|----------------------------|:---------------------------------------------------|
| D300                       | The SPDX license identifier should be Apache-2.0   |
| D301                       | The SPDX license identifier should be BSD-3-Clause |
| D302                       | The SPDX license identifier should be MIT          |
