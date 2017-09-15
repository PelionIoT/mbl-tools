# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:xenial-20170517.1

RUN apt-get update && apt-get install gosu
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Use the 'exec' form of ENTRYPOINT to ensure that docker run
# invocation arguments are appended to the command line.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

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
    debianutils \
    diffstat \
    gawk \
    gcc-multilib \
    git-core \
    iputils-ping \
    libsdl1.2-dev \
    python \
    python3 \
    python3-pexpect \
    python3-pip \
    socat \
    texinfo \
    unzip \
    wget \
    xterm \
    xz-utils

RUN rm -rf /var/lib/apt/lists/*

# The build process needs working space to perform the build and
# delivery the build products.
RUN mkdir -m 777 /work

# Make TUN available for qemu
RUN mkdir -p /dev/net \
    && mknod /dev/net/tun c 10 200 \
    && chmod 600 /dev/net/tun

COPY git-setup.sh ssh-setup.sh build.sh ./
