# Mbed Linux OS mbl-tools Repository

### Purpose

This repository provides a collection of tools and recipes related to
the build and test of Mbed Linux OS.

For more information about Mbed Linux OS, please see [meta-mbl][meta-mbl].

### Building Mbed Linux OS (MBL) ###

#### Quick Start

The run-me.sh script will create and launch a docker container to
encapsulate the Mbed Linux build environment then launch a build
script, build.sh, inside the container to do the heavy lifting.

There are a variety of options controlling what is built and how. The general form of a run-me.sh invocation is:

```
./mbl-tools/build-mbl/run-me.sh [RUN-ME.SH OPTIONS]... -- [BUILD.SH OPTIONS]...
```

Note the use of -- to separate options to run-me.sh from options that
are passed through to build.sh

Mandatory options for build-mbl/run-me.sh:
```
--builddir PATH       Specify the root of the build tree.
-o, --outputdir PATH  Specify a directory to store built artifacts.
```

Mandatory options for build-mbl/build.sh:
```
--branch BRANCH       Name the mbl-manifest branch to checkout.
--machine MACHINE     Yocto MACHINE to build. Repeat --machine option to build more than one machine.
```

Different branches of Mbed Linux can be checkout and built by passing
the --branch option through to build.sh.  The bleeding edge of
mainline development takes place on the 'master' branch.  Release
branches include: 'mbl-os-0.5', etc.

For example, to build the tip of the master branch for Raspberry Pi 3:

```
./mbl-tools/build-mbl/run-me.sh --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl
```

The build process involves the download of many source artifacts.  It
is possible to cache downloaded source artifacts between successive
builds.  In practice the cache mechanism is considered to be robust
for successive builds.  It should not be used for parallel builds.

For example, to designate a directory to hold cached downloads
between successive builds, pass the --downloaddir option to run-me.sh:

```
./mbl-tools/build-mbl/run-me.sh --builddir my-build-dir --outputdir artifacts --downloaddir my-downloads-dir -- --branch master --machine raspberrypi3-mbl
```

The build scripts will create by default the build and output directories
if they don't exist.

Use the --help option to the run-me.sh script to get brief usage
information.

#### Supported machines

mbl-tools currently builds for the following machines:

* raspberrypi3-mbl
* imx7s-warp-mbl
* imx7d-pico-mbl
* imx8mmevk-mbl

#### Build Artifacts

Each build will produce a variety of build artifacts including a
pinned manifest, target specific images and license information.

To get build artifacts out of a build, pass the --outputdir option to
specify which directory the build artifacts should be placed in:

```
./mbl-tools/build-mbl/run-me.sh --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl
```

#### Pinned Manifests and Rebuilds

Each build produces a pinned manifest as a build artifact.  A pinned
manifest is a file that encapsulates sufficient version information to
allow an exact rebuild.

To get the pinned manifest for a build, use the --outputdir option to
get the build artifacts:

```
./mbl-tools/build-mbl/run-me.sh --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl
```

This will produce the file: pinned-manifest.xml in the directory
specified with --outputdir.

To re-build using a previously pinned manifest use the --external-manifest option:

```
./mbl-tools/build-mbl/run-me.sh --external-manifest pinned-manifest.xml --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl
```

#### Mbed Cloud Client Credentials

The current Mbed Cloud Client requries key material to be statically
built into the cloud client binary.  This is a temporary measure that
will be replaced with a dynamic key injection mechanism shortly.  In
the meantime, the build scripts provide a work around:

```
./mbl-tools/build-mbl/run-me.sh --inject-mcc mbed_cloud_dev_credentials.c --inject-mcc update_default_resources.c --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl
```

#### Interactive mode

The user can have an interactive shell inside the Docker build environment
with the bitbake environment setup for issuing bitbake related commands.
To achieve this the "interactive" stage needs to be passed to the build.sh
script. For example:

```
./mbl-tools/build-mbl/run-me.sh --builddir my-build-dir --outputdir artifacts -- --branch master --machine raspberrypi3-mbl interactive
```

Only one --machine option is supported and the user should have run a complete
build before using the interactive mode.
To exit from the interactive mode the user just need to enter `exit` or Ctrl+D.


### License

Please see the [License][mbl-license] document for more information.

### Contributing

Please see the [Contributing][mbl-contributing] document for more information.



[meta-mbl]: https://github.com/ARMmbed/meta-mbl/blob/master/README.md
[mbl-license]: LICENSE.md
[mbl-contributing]: CONTRIBUTING.md

