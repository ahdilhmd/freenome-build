#!/bin/bash

set -eo pipefail

pushd freenome-build || true
    python setup.py develop
    freenome-build deploy -u
popd || true

echo "build and deploy success"

exit 0