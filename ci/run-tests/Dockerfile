FROM py-deploy-base-image

ADD . /work

WORKDIR /work

# We expect the python package contains a requirements.txt to install development dependencies.
RUN pip3 install pytest && pip3 install -r requirements.txt

CMD [ "pytest", "tests/unit", "--junit-xml", "report" ]
