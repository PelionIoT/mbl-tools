# Purpose

Deploy a python package to PyPI (Python Package Index).

# Requirements

You must already have built a python 'wheel' from your python package.

The deployment is performed in a docker container. Docker is the only other pre-requisite.

# Usage

Execute the `launch_docker_container.py` script (located in ci/launch-container/) and pass in the path to the Dockerfile in this directory.

We must also pass in the `--workdir` option. 

```bash
$ python launch_docker_container.py <image-name> <container-name> path/to/mbl-tools/ci/deploy-to-pypi/Dockerfile --workdir path/to/your/python/project
```

This will launch a docker container, install twine and upload your wheel to PyPI.