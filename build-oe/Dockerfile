FROM ubuntu:xenial-20170517.1

RUN useradd -ms /bin/bash squirrel

# op-tee build.git prerequisites
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

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN rm -rf /var/lib/apt/lists/*

# The build process needs working space to perform the build and
# delivery the build products.
VOLUME /work

# Make TUN available for qemu
RUN mkdir -p /dev/net \
    && mknod /dev/net/tun c 10 200 \
    && chmod 600 /dev/net/tun

USER squirrel
WORKDIR /home/squirrel

COPY build-oe.sh .

RUN git config --global user.email "secret.squirrel@we.will.call.you.com" \
    && git config --global user.name "Secret Squirrel" \
    && git config --global color.ui false

#ENTRYPOINT ./build-optee.sh
#CMD ["--help"]
