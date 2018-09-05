#!/bin/bash

pushd ..
    python setup.py develop
    freenome-build deploy -u
popd