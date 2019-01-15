# Purpose

This folder contains tools to create and launch docker containers from a base image, for use in a ci system.

# Requirements

Docker and python 3 must be installed on your system.

# Description

At the top level of this directory, there is one python script which serves as the entry point.

* `launch_docker_container.py` The main entry point to launch and run containers.


The lib folder contains two python scripts and a Dockerfile to define a base image.

* `args.py` The argument parser for `launch_docker_container.py`

* `docker.py` Utility functions to call common docker commands.

# <a name="usage"></a>Usage

You must define a Dockerfile for your specific image/use case.

Use `FROM py-deploy-base-image` in your Dockerfile and extend the base image with any other dependencies you need.

`launch_docker_container.py` will build the `py-base-deploy-image` as a first step.

## Arguments

`launch_docker_container.py` expects several command line arguments, described below.

### Image

The name of the image to build.

### Container

The name of the container to launch.

### Dockerfile

The path to your Dockerfile (which should be based on `py-deploy-base-image` as described in the [Usage](#usage) section).

### Workdir (Optional) 

The working directory of the project. Defaults to `pwd`.

### CP (Optional) 

Copy artifacts from the docker container to `--workdir`. 

Requires a path, which is the path inside your container where the artifacts are located.
