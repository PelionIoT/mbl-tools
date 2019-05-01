FROM py-deploy-base-image

ADD . /work

WORKDIR /work

# We expect the python package contains a setup.py.
RUN pip3 install pytest && pip3 install .

CMD [ "pytest", "--junit-xml", "report" ]