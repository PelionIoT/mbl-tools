# Copyright (c) 2018, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

FROM ubuntu:xenial-20170517.1

## Build environment tooling

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN apt-get update && apt-get install -y \
    build-essential \
    chrpath \
    cpio \
    curl \
    debianutils \
    dialog \
    diffstat \
    gawk \
    gcc-multilib \
    git-core \
    iputils-ping \
    libsdl1.2-dev \
    python \
    python3 \
    python3-pip \
    socat \
    texinfo \
    tmux \
    unzip \
    wget \
    xterm \
    xz-utils \
    parted

RUN apt-get update && apt-get install gosu
RUN pip3 install -U pip
RUN pip3 install dohq-artifactory jinja2 pexpect
COPY common/entrypoint.sh /usr/local/bin/entrypoint.sh

# Use the 'exec' form of ENTRYPOINT to ensure that docker run
# invocation arguments are appended to the command line.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

RUN rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/bin \
    && curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo \
    && chmod a+x "/usr/local/bin/repo"

# Make TUN available for qemu
RUN mkdir -p /dev/net \
    && mknod /dev/net/tun c 10 200 \
    && chmod 600 /dev/net/tun

# Scripts used to build mbed-linux image
COPY common/git-setup.sh common/ssh-setup.sh \
     templates/README.binary_release_template \
     templates/Licensing_and_Acknowledgment.template_nxp \
     license-report ./
COPY mbl/build.sh common/config-funcs.sh ./

# Scripts used to build poky-psa image
COPY poky-test/build-poky.py \
     common/file_util.py \
     poky-test/poky-bitbake-wrapper.sh ./

# Scripts used to build BL2/BL3/fitImage components
COPY common/bitbake_util.py \
     mbl/build-update-payloads.py ./