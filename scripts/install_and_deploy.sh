#!/bin/bash

pushd freenome-build
    python setup.py develop
    freenome-build deploy -u
popd
