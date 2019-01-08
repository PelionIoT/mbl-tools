# Purpose

Tooling to run python unit tests in a docker container.

# Requirements

The tests are executed in a docker container. Therefore docker must be installed on your system.

The Dockerfile expects that your python package contains a file named ["requirements.txt"](https://pip.readthedocs.io/en/1.1/requirements.html), at the top level of the directory tree. 

The requirements.txt is used to install the package dependencies in the docker container.

The tests are executed using pytest, therefore your unit tests must follow the [Conventions for Python test discovery](https://docs.pytest.org/en/latest/goodpractices.html)

# Usage

```bash
$ ./run-tests.sh --workdir path/to/your/python/project
```

This will run your unit tests in a docker container using pytest.

The script will copy the test results, in junit xml format, to the top level of `--workdir`.