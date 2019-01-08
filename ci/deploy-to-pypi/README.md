# Purpose

Deploy a python package to PyPI (Python Package Index).

# Requirements

You must already have built a python 'wheel' from your python package to use this script.

You must place your pypi credentials in a config file, in the same directory as the wheel.

The deployment is performed in a docker container. Docker is the only other pre-requisite.

# Usage

Assuming docker is installed on your system.

```bash
$ ./deploy-to-pypi.sh --workdir path/to/your/python/wheel
```

This will launch a docker container, install twine and upload your wheel to PyPI