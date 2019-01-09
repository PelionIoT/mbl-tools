# Purpose

This folder contains some libraries and a base Dockerfile to use with python packages.

# Requirements

The tests are executed in a docker container. Therefore docker must be installed on your system.

# Description

The library contains two shell scripts and a Dockerfile to define a base image.

`parse-args.sh` contains a function which handles a `--workdir` long option and a standard `--help` option.

The argument handler expects your shell script contains a `usage` function which prints the help text.

`build-py-base-image.sh` builds the base image for your docker containers. The image will be named `py-deploy-base-image`.

`py-deploy-base-image` extends `ubuntu:bionic-20180724.1` by installing `python 3.6` and `pip`.

# Usage

You can use `FROM py-deploy-base-image` in your Dockerfile and extend with any other dependencies you need.

You must first ensure the image has been built, by executing the `buildPyBaseImage` function in your shell script.

## parse-args.sh

First we need to 'import' the script

```bash
. /lib/parse-args.sh
```

Then the `workdirAndHelpArgParser` function should be available. You must pass all command line args in to the function

```bash
workdirAndHelpArgParser "$@"
```

## build-py-base-image.sh

Again, we must import the script

```bash
. /lib/build-py-base-image.sh
```

Now the `buildPyBaseImage` function should be available. You must pass the path to the `lib` folder in to the function

```bash
buildPyBaseImage "/lib/"
```

