#!/usr/bin/env bash

set -eo pipefail

ANACONDA_TOKEN=$1
if [ $(uname) = 'Linux' ]; then
    MINICONDA_URL='https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh'
elif [ $(uname) = 'Darwin' ]; then
    MINICONDA_URL='https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh'
else
    echo "We do not support $(uname) architecture at this time"
    exit 1
fi
MINICONDA_INSTALL_PATH=$HOME/miniconda

mkdir -p $MINICONDA_INSTALL_PATH

pushd $MINICONDA_INSTALL_PATH
    # check for conda install, and install if necessary
    CONDA_INSTALLED=1
    command -v conda >/dev/null 2>&1 || CONDA_INSTALLED=0
    if [[ $CONDA_INSTALLED -eq 0 ]]; then
        # install conda
        curl -sO $MINICONDA_URL;
        bash $(basename $MINICONDA_URL) -b -u -p $MINICONDA_INSTALL_PATH;
        # activate the base conda environment
        export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH";
        source "$MINICONDA_INSTALL_PATH/etc/profile.d/conda.sh";
        conda install anaconda-client --yes
    fi

    # setup the condarc with the correct set of channels
    conda config --remove channels defaults || true
    conda config --add channels https://repo.anaconda.com/pkgs/pro/
    conda config --add channels https://repo.anaconda.com/pkgs/free/
    conda config --add channels https://repo.anaconda.com/pkgs/main/
    conda config --add channels conda-forge
    conda config --add channels bioconda
    conda config --add channels https://conda.anaconda.org/t/$ANACONDA_TOKEN/freenome

    # install freenome-build. If we are building a new tag, assume it's a good
    # tag, and use the build files on disk, instead of downloading the latest
    # stable install. (If we push a bad install we can get in a situation where
    # we're downloading the bad install and then can't ever use the bad install
    # to update, which is bad).
    #
    # Travis env vars: https://docs.travis-ci.com/user/environment-variables/
    if [[ "${TRAVIS_TAG:-}" ]]; then
        conda install conda-build --yes
        pushd "${TRAVIS_BUILD_DIR}"
            python setup.py install
        popd
    else
        conda install freenome-build --yes
    fi
popd
