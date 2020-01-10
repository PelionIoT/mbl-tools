# Copyright (c) 2020 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

FROM ubuntu:19.10

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# Add an apt repository containing the clang-9 packages.
# We need clang-9 and its c++17 support for our C++ code.
RUN apt-get install -y software-properties-common wget
RUN add-apt-repository ppa:ubuntu-toolchain-r/test
RUN apt-get update && apt-get install -y \
    git \
    xz-utils \
    build-essential \
    autoconf \
    libtool \
    pkg-config \
    libtinfo5 \
    libncurses-dev \
    curl \
    cmake \
    make \
    clang-9 \
    clang-tidy-9 \
    g++ \
    unzip

# Install project dependencies for mbl-core/updated
RUN apt-get install -y libsystemd-dev

RUN rm -rf /var/lib/apt/lists/*

# UpdateD requires protoc and gRPC, we need to build from source to get the gRPC
# CPP runtime.
# Configure protoc for the build.
RUN git clone https://github.com/protocolbuffers/protobuf.git \
    && cd protobuf \
    && git submodule update --init --recursive \
    && ./autogen.sh

# Build and install protoc.
RUN cd protobuf \
    && ./configure \
    && make && make check && make install \
    && ldconfig

# Build and install gRPC.
RUN git clone -b v1.25.0 https://github.com/grpc/grpc \
    && cd grpc \
    && git submodule update --init \
    && make && make install
