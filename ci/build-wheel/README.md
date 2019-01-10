# Purpose

Tooling to build a python wheel binary in a docker container.

# Requirements

Docker must be installed on your system.

The Dockerfile expects that your python package contains a file named ["requirements.txt"](https://pip.readthedocs.io/en/1.1/requirements.html), at the top level of the directory tree. 

The requirements.txt is used to install the package dependencies in the docker container.

# Usage

Execute the `launch_docker_container.py` script (located in ci/launch-container/) and pass in the path to the Dockerfile in this directory.

We must also pass in the `--workdir` and `--cp` options. 

```bash
$ python launch_docker_container.py <image-name> <container-name> path/to/mbl-tools/ci/build-wheel/Dockerfile --workdir path/to/your/python/project --cp work/dist
```

This will run a docker container and build the wheel ready for deployment.

The script will copy the build artifacts to `path/to/your/python/project/dist`
