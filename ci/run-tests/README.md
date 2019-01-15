# Purpose

This directory contains a Dockerfile to run python unit tests in a docker container.

# Requirements

The tests are executed in a docker container. Therefore docker must be installed on your system.

The Dockerfile expects that your python package contains a file named ["requirements.txt"](https://pip.readthedocs.io/en/1.1/requirements.html), at the top level of the directory tree. 

The requirements.txt is used to install the package dependencies in the docker container.

The tests are executed using pytest, therefore your unit tests must follow the [Conventions for Python test discovery](https://docs.pytest.org/en/latest/goodpractices.html)

# Usage

Execute the `launch_docker_container.py` script (located in ci/launch-container/) and pass in the path to the Dockerfile in this directory.

We must also pass in the `--workdir` and `--cp` options. 

```bash
$ python launch_docker_container.py <image-name> <container-name> path/to/mbl-tools/ci/run-tests/Dockerfile --workdir path/to/your/python/project --cp work/report
```

This will run your unit tests in a docker container using pytest.

The script will copy the test results, in junit xml format, to the top level of `--workdir`.