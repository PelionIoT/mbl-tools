# Copyright (c) 2020 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

FROM ubuntu:bionic-20180724.1

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN apt-get update && apt-get install -y \
    cmake \
    make \
    clang-tidy \
    clang

# Install project dependencies for mbl-core/updated
RUN apt-get install -y libsystemd-dev

RUN rm -rf /var/lib/apt/lists/*

# The build process needs working space to perform the build and
# delivery the build products.
RUN mkdir -m 777 /work

COPY clang-tidy-check.sh ./
