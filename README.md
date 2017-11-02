# README #

This repository provides a collection of tools and recipes related to
the build and test of mbed Linux.

### Building Mbed Linux (MBL) ###

#### Quick Start

Build MBL for Raspberry PI 3 (RPi3):

Checkout and build the tip of the master branch for mbed linux:

```
./mbl-tools/build-mbl/run-me.sh
```

The run-me.sh script will create and launch a docker container to
encapsulate the mbed linux build environment then launch a build
script, build.sh, inside the container to do the heavy lifting.

There are a variety of options controlling what is built and how. The general form of a run-me.sh invocation is:

```
./mbl-tools/build-mbl/run-me.sh [RUN-ME.SH OPTIONS]... -- [BUILD.SH OPTIONS]...
```

Note the use of -- to separate options to run-me.sh from options that
are passed through to build.sh

Different branches of mbed linux can be checkout and built by passing
the --branch option through to build.sh.  The bleeding edge of
mainline development takes place on the 'master' branch.  Release
branches include: 'rocko', 'pyro' etc

For example, to build the tip of the rocko release branch:

```
./mbl-tools/build-mbl/run-me.sh -- --branch=rocko
```

The build process involves the download of many source artifacts.  It
is possible to cache downloaded source artifacts between successive
builds.  In practice the cache mechanism is considered to be robust
for successive builds.  It should not be used for parallel builds.

For example, to designate a directory to hold cached downloads
between successive builds, pass the --downloaddir option to run-me.sh:

```
mkdir downloads
./mbl-tools/build-mbl/run-me.sh --downloaddir=$(pwd)/downloads -- --branch=rocko
```

The build scripts will by default create and use a build directory
under the current working directory.  An alternative build directory
can be specified using the --builddir option to run-me.sh:

```
./mbl-tools/build-mbl/run-me.sh --builddir=my-build-dir --branch=master
```

Use the --help option to the run-me.sh script to get brief usage
information.

#### Build Artifacts

Each build will produce a variety of build artifacts including a
pinned manifest, target specific images and license information.

To get build artifacts out of a build, pass the --outputdir option to
specify which directory the build artifacts should be placed in:

```
mkdir artifacts
./mbl-tools/build-mbl/run-me.sh --outputdir=artifacts --branch=master
```

#### Pinned Manifests and Rebuilds

Each build produces a pinned manifest as a build artifact.  A pinned
manifest is a file that encapsulates sufficient version information to
allow an exact rebuild.

To get the pinned manifest for a build, use the --outputdir option to
get the build artifacts:

```
mkdir artifacts
./mbl-tools/build-mbl/run-me.sh --outputdir=artifacts --branch=master
```

This will produce the file: pinned-manifest.xml in the directory
specified with --outputdir.

To re-build using a previously pinned manifest use the --external-manifest option:

```
./mbl-tools/build-mbl/run-me.sh --external-manifest=pinned-manifest.xml
```

#### mbed Cloud Client Credentials

The current mbed Cloud Client requries key material to be statically
built into the cloud client binary.  This is a temporary measure that
will be replaced with a dynamic key injection mechanism shortly.  In
the meantime, the build scripts provide a work around:

```
./mbl-tools/build-mbl/run-me.sh --inject-mcc mbed_cloud_dev_credentials.c --inject-mcc update_default_resources.c --
```

### Building OP-TEE ###

#### Quick Start

Build OP-TEE for Raspberry PI 3 (RPi3):

```
./mbl-tools/build-optee/run-me.sh --target rpi3
```

### OP-TEE Build Image

The op-tee build image provides a canned docker image capable of build
a minimal OP-TEE system using https://github.com/OP-TEE/manifest.git

The image contains a base ubuntu image with minimal set of tools
required and a script to drive the build process.  The image is
typically used to spin up a container and execute the build script
build.sh.  The directory used for the build can be passed to the
build.sh script by argument.  Typical usage would be to map a
build directory into the container as the volume path /optee.
