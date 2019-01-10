FROM py-deploy-base-image

RUN mkdir -m 777 /work
ADD . /work

WORKDIR /work

# We expect the python package contains a requirements.txt to install development dependencies.
RUN pip3 install -r requirements.txt

CMD ["python3", "setup.py", "bdist_wheel"]
