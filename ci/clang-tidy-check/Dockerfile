# Copyright (c) 2020 Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

FROM rwalton00/mbl-sanity-checks:test

RUN git clone https://github.com/gabime/spdlog.git \
    && cd spdlog && mkdir build && cd build \
    && cmake -DCMAKE_CXX_CLANG_TIDY="" .. && make -j && make install

# Create a work directory to copy the target dir into.
RUN mkdir -m 777 /work

# CMake segfaults when run from the root directory,
# so put it in its own script dir.
RUN mkdir -m 777 /script

COPY clang-tidy-check.sh /script/clang-tidy-check.sh
WORKDIR /script
