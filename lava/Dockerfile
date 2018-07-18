# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM python:3.7-alpine3.7

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python" ]