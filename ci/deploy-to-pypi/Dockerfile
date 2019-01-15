FROM py-deploy-base-image

ADD . /work

WORKDIR /work

RUN pip3 install twine

CMD ["twine", "upload", "./*.whl"]
