#!/bin/env/python

"""
This module is for building and running docker containers based on a 'py-deploy-base-image'.

The first step builds the 'py-deploy-base-image', which is based on ubuntu:bionic-20180724.1.
The base image also includes Python3.6 and pip. 
We will then attempt to build an extended image from the dockerfile provided. 
A docker container is then launched, optionally copying any artifacts back to the workdir.
"""

import os

from lib import args, docker


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DOCKERFILE_PATH = os.path.join(SCRIPT_DIR, "lib", "Dockerfile")


def _main():
    """Entry point."""
    cli_args = args.parse_args()
    # Build the base image first
    docker.build("-t", "py-deploy-base-image", "-f", BASE_DOCKERFILE_PATH, SCRIPT_DIR)
    # Extend with specific image
    docker.build("-t", cli_args.image, "-f", cli_args.dockerfile, cli_args.workdir)
    # Run the container
    docker.run("--name", cli_args.container, cli_args.image)
    # Copy artifacts if required
    if cli_args.cp:
        docker.cp("{}:{}".format(cli_args.container, cli_args.cp), cli_args.workdir)
    # Clean up
    docker.rm(cli_args.container)


if __name__ == "__main__":
    _main()
