import os
import sys
import re
import subprocess
import conda
import conda_build.api

def setup_development_environment(path='./', environment_name=None):
    # set the default environment name
    if environment_name is None:
        environment_name = subprocess.run(
            'git describe --all HEAD^',
            shell=True,
            stdout=subprocess.PIPE
        ).stdout.strip().decode('utf8').replace('/', '__')

    # build the package.
    # ( we need to do this to install the dependencies -- which is super hacky but required
    #   because of the jinja templating -- see https://github.com/conda/conda/issues/5126   )
    yaml_fpath = os.path.normpath(os.path.abspath(os.path.join(path, "conda-build/meta.yaml")))
    if not os.path.exists(yaml_fpath):
        raise ValueError(f"Could not find a yaml file at '{yaml_fpath}'")
    output_file_paths = conda_build.api.build(
        [yaml_fpath,],
        skip_existing=True
    )
    print(output_file_paths)
    assert False



def environment_build_and_upload(path='./', upload=True):
    # Set the environment variable VERSION so that
    # the jinja2 templating works for the conda-build
    with open('lims_api/__init__.py', 'r') as fp:
        version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                            fp.read(), re.MULTILINE).group(1)
    local_env = os.environ
    local_env['VERSION'] = version

    # build the package
    yaml_fpath = os.path.normpath(os.path.abspath(os.path.join(path, "conda-build/meta.yaml")))

    output_file_paths = conda_build.api.build(
        [yaml_fpath,],
        skip_existing=False
    )

    if upload:
        upload_cmd = ['anaconda', '-t', local_env['ANACONDA_TOKEN'],
                      'upload', '-u', 'freenome', output_file_paths[0]]

        output = subprocess.check_output(upload_cmd)


def main():
    if sys.argv[1] == 'develop':
        setup_development_environment()

if __name__ == '__main__':
    main()
