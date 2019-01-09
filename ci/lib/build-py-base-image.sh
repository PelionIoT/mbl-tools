#!/bin/bash

set -e

buildPyBaseImage(){
  docker build -t py-deploy-base-image -f "$1"/Dockerfile .
}
