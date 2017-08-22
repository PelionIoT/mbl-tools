# README #

This repository provides a collection of tools and recipes related to the build and test of mbed Linux.

### Building OP-TEE ###

* Build the docker image encapsulating the OP-TEE build environment:

```
docker build -t optee ./mbl-tools/build-optee/
```

* Create a work space to contain the build:

```
mkdir build-optee
```

* Execute the build:

```
docker run -v $(pwd)/build-optee:/optee optee ./build-optee.sh --builddir /optee --target rpi3
```

### OP-TEE Build Image

The op-tee build image provides a canned docker image capable of build
a minimal OP-TEE system using https://github.com/OP-TEE/manifest.git

The image contains a base ubuntu image with minimal set of tools
required and a script to drive the build process.  The image is
typically used to spin up a container and execute the build script
build-optee.sh.  The directory used for the build can be passed to the
build-optee.sh script by argument.  Typical usage would be to map a
build directory into the container as the volume path /optee.

### Raspberry PI 3 Open Embedded Build

* Build the docker image encapsulating the OE build environment:

```
docker build -t oe ./mbl-tools/build-oe
```

* Execute the build:

```
docker run -v $(pwd)/build-oe:/work oe ./build-oe.sh --builddir /work
```

### Raspberry PI 3 Mbed Linux Build

#### Quick Start

Build mbed linux for Raspberry PI 3 (RPi3):

```
./mbl-tools/build-mbl/run-me.sh
```

#### Under the Hood

The run-me.sh script encapsulates two steps:
1) Construct a docker environment capable of build mbed-linux.
2) Build mbed-linux in a docker environment.
