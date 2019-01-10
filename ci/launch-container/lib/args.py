#!/bin/env/python

import argparse
import os


def parse_args():
    """Parse cli arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "image",
        help="Name of the image to create."
    )

    parser.add_argument(
        "container",
        help="Name of the container to create."
    )

    parser.add_argument(
        "dockerfile",
        help="Path to the Dockerfile."
    )

    parser.add_argument(
        '-w',
        '--workdir',
        default=os.getcwd(),
        help="The working directory to add to the container."
    )

    parser.add_argument(
        "--cp",
        help="Copy files from the container. " 
        "Requires a path (inside the container) to copy any artifacts from. "
        "Artifacts will be copied to --workdir."
    )

    return parser.parse_args()
