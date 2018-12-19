# Content

Here the list of files present in this directory.

* `Dockerfile`: it is used to create a container with all dependencies needed
for running submit-to-lava.py and its tests
* `lava-job-definitions` directory: it contains job jinja2 templates which are
populated and submitted to LAVA
* `README.md`: this file
* `requirements.txt`: python dependencies. This file is automatically used by
the docker image creation. Otherwise it can be used by the user to install
dependencies in his/her own environment
* `run-me.sh`: bash script which encapsulates docker logic for running python
scripts
* `submit-to-lava.py`: python script used to submit jobs to LAVA. See below how
to run it
* `tests` directory: unit tests for submit-to-lava.py (pytest is the framework
of choice). See below how to run them.

# Docker vs native

Docker is used to set up an environment where all dependencies are installed
for running submit-to-lava.py and its unit tests. Those are python libraries
and the content of this directory. This is facilitated by run-me.sh and
Dockerfile.
A user though might decide not to user docker at all and run the script in
his/her own environment. Required libraries are listed in requirements.txt
file.

# LAVA client

## LAVA installation
Before submitting a job to LAVA, you should have a running infrastructure where
to submit jobs to. More info: https://validation.linaro.org/static/docs/v2/

## Submit jobs to LAVA
In order to submit jobs to LAVA you need at least the following info (these are
mandatory parameters to submit-to-lava.py):

* lava-server: lava server url
* lava-username: user used for LAVA authentication
* lava-token: token used for LAVA authentication
* device-type: device-type where to run tests
* imege-url: a http url where to download the image from

For more option you might refer to the help of the script:

```
$ ./run-me.sh -c submit -- -h
```

An example command to submit a job is:

```
$ ./run-me.sh -c submit -- \
    --device-type imx7s-warp \
    --lava-server http://mbl-lava-master-dev.com \
    --image-url http://example.com/mbl-image-release-imx7s-warp-mbl.wic.gz \
    --lava-username dierus01 \
    --lava-token tokentest
```

It will output a list of urls which are used to check jobs details.

# Testing submit-to-lava.py

In order to test submit-to-lava.py it's enough to run the following command:

```
$ ./run-me.sh -x -c test
```

The command builds the container with all required dependencies and then it
invokes pytest.

If you want more debug, you might run:

```
./run-me.sh -x -c test -- -v
```
