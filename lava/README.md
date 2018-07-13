# LAVA client

## LAVA installation
Before submitting a job to LAVA, you should have a running infrastructure where
to submit jobs to. More info: https://validation.linaro.org/static/docs/v2/

## Submit jobs to LAVA
In order to submit jobs to LAVA you need at least the following info:

* lava-server: lava server url
* lava-username: user used for LAVA authentication
* lava-token: token used for LAVA authentication
* device-type: device-type where to run tests
* imege-url: a http url where to download the image from

For more option you might refer to the help of the script:

```
$ docker build -t python3.7 . && docker run -it --rm python3.7 submit-to-lava.py -h
```

An example command to submit a job is:

```
$ docker build -t python3.7 . && docker run -it --rm python3.7 submit-to-lava.py
    --device-type imx7s-warp \
    --lava-server http://mbl-lava-master-dev.com \
    --image-url http://example.com/mbl-console-image-imx7s-warp-mbl.wic.gz \
    --lava-username dierus01 \
    --lava-token tokentest
```

It will output a list of urls which are used to check jobs details.

# Testing submit-to-lava.py

In order to test submit-to-lava.py it's enough to run the following command:

```
$ docker build -t python3.7 . && docker run -it --rm python3.7 -m pytest
```

The command builds the container with all required dependencies and then it
invokes pytest.
