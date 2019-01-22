<!-- Copyright (c) 2019 Arm Limited and Contributors. All rights reserved.

SPDX-License-Identifier: BSD-3-Clause -->
# What licensing checks are running?

The [`mbl-licensing-checker`] python application checks for expected licenses and copyright notices on first and third party source files.

The sanity check script fails if the application returns a non-zero exit code.

## Requirements

The easiest way is to run it through Docker, hence the only requirement is to have Docker installed.

To run it natively, install the [`mbl-licensing-checker`] application.

## Usage

### Running with Docker

```
$ ./run-me.sh --workdir /path/to/file/or/directory
```

The script runs the [`mbl-licensing-checker`] application within a Docker container which contains all required dependencies.
The output will be printed on the screen with the result.

### Running natively

```
$ ./licensing-check.sh --workdir /path/to/file/or/directory
```

The script runs the [`mbl-licensing-checker`] application natively.
The output will be printed on the screen with the result.

### Skipping directories

You can disable sanity check for a specific sub-tree by placing an [`mbl-licensing-checker`] configuration file with the convention set to none. See [here](../../mbl-licensing-checker/README.md) for more information.

[`mbl-licensing-checker`]: ../../mbl-licensing-checker
