# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:xenial-20170517.1

RUN useradd -ms /bin/bash squirrel

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

RUN apt-get update && apt-get install -y \
    dialog
  
RUN rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/bin \
    && curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo \
    && chmod a+x "/usr/local/bin/repo"

# The build process needs working space to perform the build and
# delivery the build products.
VOLUME /work

# Make TUN available for qemu
RUN mkdir -p /dev/net \
    && mknod /dev/net/tun c 10 200 \
    && chmod 600 /dev/net/tun

USER squirrel
WORKDIR /home/squirrel

RUN git config --global user.email "secret.squirrel@we.will.call.you.com" \
    && git config --global user.name "Secret Squirrel" \
    && git config --global color.ui false

RUN host="github.com" \
    && mkdir -p ~/.ssh \
    && chmod 700 ~/.ssh \
    && touch ~/.ssh/known_hosts \
    && chmod 600 ~/.ssh/known_hosts \
    && if ! ssh-keygen -F "$host" > /dev/null; then \
         ssh-keyscan -H "$host" >> ~/.ssh/known_hosts; \
       fi \
    && cat ~/.ssh/known_hosts
      
COPY build.sh .

#ENTRYPOINT ./build.sh
#CMD ["--help"]
