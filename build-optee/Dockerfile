# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:xenial-20170517.1

RUN useradd -ms /bin/bash squirrel
RUN apt-get update && apt-get install -y \
    emacs

# op-tee build.git prerequisites
RUN apt-get update && apt-get install -y \
    emacs

RUN apt-get install -y \
    android-tools-adb \
    android-tools-fastboot \
    autoconf \
    automake \
    bc \
    bison \
    build-essential \
    cscope \
    curl \
    device-tree-compiler \
    flex \
    ftp-upload \
    gdisk \
    iasl \
    libattr1-dev \
    libcap-dev \
    libfdt-dev \
    libftdi-dev \
    libglib2.0-dev \
    libhidapi-dev \
    libncurses5-dev \
    libpixman-1-dev \
    libssl-dev \
    libtool \
    make \
    mtools \
    netcat \
    python-crypto \
    python-serial \
    python-wand \
    unzip \
    uuid-dev \
    xdg-utils \
    xterm \
    xz-utils \
    zlib1g-dev

# The optee build environment installs i386 toolchains hence
# we need multi arch support for i386.
RUN dpkg --add-architecture i386 \
    && apt-get update && apt-get install -y \
    libc6:i386 \
    libstdc++6:i386 \
    libz1:i386

RUN apt-get update && apt-get install -y \
    git \
    wget

RUN rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/bin \
    && curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo \
    && chmod a+x "/usr/local/bin/repo"

# The build process needs working space to perform the build and
# delivery the build products.
VOLUME /work

USER squirrel
WORKDIR /home/squirrel

COPY git-setup.sh ssh-setup.sh build.sh ./

#ENTRYPOINT ./build.sh
#CMD ["--help"]
