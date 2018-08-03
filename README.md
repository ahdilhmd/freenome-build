# This is alpha quality software and should not be used for production workloads

# freenome-build
Packaging, build, and development tools.

## freenome-build db
Manage a test postgres DB in a Docker container. This also runs a DB setup script and DB migrations. The structure of the setup and migrations scripts is described in more detail in the  [README](./freenome_build/database_template/README.md)

## freenome-build db start-local-test-db
Start a test DB with test data. Returns a connection string to stdout

## freenome-build db stop 
Stop a test DB.

## freenome-build develop
Setup a conda development environment for the current repo.

Running `freenome-build develop $REPO_PATH` sets up a development environment for the github repo in $REPO_PATH. Specifically, this command:
1) builds a conda package
   - if a meta.taml file exists in `$REPO_PATH/meta.yaml` then use that as the package specification
   - if not, use `python setup.py bdist_conda` to build the conda package
2) install the built packages' dependencies by running `conda install $PACKAGE --only-deps`
3) install the package in python's develop mode by running `python $REPO_PATH/setup.py develop` 

## freenome-build deploy -u -p $REPO_PATH
Build the package in $REPO_PATH and upload to anaconda cloud. The -u flag asks freenome-build to upload to anaconda cloud in addition to packaging.


## Caveats, gotchas, and TODO's
The package name is inferred from:
1) the github repo name

__TODO__ Allow the package name to be specified as an argument

The package version is inferred from:
1) a version file at $REPO_PATH/VERSION
2) a `__version__` string in $REPO_PATH/$MODULE_NAME that amtches the pattern `^__version__\s*=\s*[\'"]([^\'"]*)[\'"]`

__TODO__ Allow version to be specified as an argument

## Bootstrapping requires scripts/conda_build.sh
Each repo must clone the freenome-build repo during a travis build so that it can call `scripts/conda_build.sh`. This requires that that repo on travis has a github access token generated locally using the ruby travis script. For example for LIMS-API I ran the following

```bash
travis endpoint --pro --set-default
travis login
travis sshkey --generate -r freenome/LIMS-API     --debug
```

In order to clone from freenome's conda channel in a `.travis.yml` you need an anaconda token to be securely encrypted


```bash
travis endpoint --pro --set-default
travis login
travis encrypt ANACONDA_TOKEN=[ANACONDA_TOKEN] --add
```
