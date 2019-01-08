# Purpose

Tooling to build a python wheel binary in a docker container.

# Requirements

The script launches a docker container to build the wheel. Therefore docker must be installed on your system.

The Dockerfile expects that your python package contains a file named ["requirements.txt"](https://pip.readthedocs.io/en/1.1/requirements.html), at the top level of the directory tree. 

The requirements.txt is used to install the package dependencies in the docker container.

# Usage

```bash
$ ./build-wheel.sh --workdir path/to/your/python/project
```

This will run a docker container and build the wheel ready for deployment.

The script will copy the build artifacts to `path/to/your/python/project/dist`