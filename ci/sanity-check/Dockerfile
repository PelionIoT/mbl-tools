# Copyright (c) 2018 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM ubuntu:bionic-20180724.1

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    shellcheck

RUN pip3 install pycodestyle pep257 black

RUN rm -rf /var/lib/apt/lists/*

# The build process needs working space to perform the build and
# delivery the build products.
RUN mkdir -m 777 /work

COPY sanity-check.sh tab_finder.py ./
