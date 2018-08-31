SHELL = /bin/bash -o pipefail

# Don't load virtualenv if we are already running in one.
ifeq ($(VIRTUAL_ENV),)
VIRTUALENV_PREAMBLE := . venv/bin/activate;
endif

venv:
ifeq ($(VIRTUAL_ENV),)
	pip install --upgrade pip
	pip install --upgrade virtualenv
	virtualenv --python=python3.6 venv
endif

install: venv
	$(VIRTUALENV_PREAMBLE) pip install -r update_requirements.txt
	# this adds additional packages; would be great to move to
	# test-requirements.txt like the other packages.
	$(VIRTUALENV_PREAMBLE) python setup.py install

lint: venv
	$(VIRTUALENV_PREAMBLE) python -m flake8 freenome_build

test: venv
	$(VIRTUALENV_PREAMBLE) python -m pytest --duration=0 tests

bail: venv
	$(VIRTUALENV_PREAMBLE) python -m pytest --maxfail=1 tests
