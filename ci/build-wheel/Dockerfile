FROM ubuntu:bionic-20180724.1

RUN apt-get update && apt-get install locales \
    && dpkg-reconfigure locales \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip

ADD . /work

WORKDIR /work

RUN pip3 install -r requirements.txt

CMD ["python3", "setup.py", "bdist_wheel"]
