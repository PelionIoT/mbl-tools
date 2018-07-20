# Copyright (c) 2017 ARM Ltd.
#
# SPDX-License-Identifier: Apache-2.0

FROM python:3.7-alpine3.7

# Change working directory
WORKDIR /usr/src/app

# Copy requirements.txt to root and install python dependecies with pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy every file present in the Dockerfile directory to the working directory
# of the image (/usr/src/app).
COPY . .

# Set the container entrypoint to be the python interpreter. This is executed
# in the working directory and it has visibility of the file copied in the
# previous command
ENTRYPOINT [ "python" ]