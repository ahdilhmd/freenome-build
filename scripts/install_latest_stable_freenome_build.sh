#!/usr/bin/env bash

ANACONDA_TOKEN=$1
MINICONDA_URL=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
MINICONDA_INSTALL_PATH=$HOME/miniconda

# check for conda install, and install if neessary
CONDA_INSTALLED=1
command -v conda >/dev/null 2>&1 || CONDA_INSTALLED=0
if [[ $ANACONDA_INSTALLED -eq 0 ]]; then
    #install conda
    wget $MINICONDA_URL
    bash $( basename $MINICONDA_URL ) -b -p $MINICONDA_INSTALL_PATH
    export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH"
fi

# enable access to freenome channel
conda config --add channels conda-forge
conda config --add channels bioconda
conda config --add channels https://conda.anaconda.org/t/$ANACONDA_TOKEN/freenome

# install freenome-build
conda install freenome-build --yes
