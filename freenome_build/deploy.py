import os
import sys
import subprocess

from freenome_build.util import build_package
from freenome_build import version_utils

LOCAL_CONDA_BUILD_SCRIPT = os.path.abspath('scripts/conda_build.sh')


def build_and_upload_package_from_repo(path='./', upload=True, skip_existing=False, package_name=None, all=False):
    """

    Args:
        path (str): library path to install (default './')
        upload (bool): upload to freenome conda channel (default True)
        skip_existing (bool): do not build if existing build in local conda install (default False)
        package_name (str): name to build package into upon upload to freenome conda (optional)
        all (bool): build conda package for all platforms

    Returns:
        None

    """
    version = version_utils.version(path)

    output_file_path = build_package(path, version, skip_existing=skip_existing)

    if upload:
        upload_cmd = ['anaconda', '-t', os.environ['ANACONDA_TOKEN'],
                      'upload', '--force', '-u']

        if package_name is not None:
            upload_cmd += ['--package', package_name]

        if all:
            upload_cmd += ['--all']

        upload_cmd +=['freenome', output_file_path]

        subprocess.check_call(upload_cmd, stdout=sys.stdout, stderr=sys.stderr)


def deploy_main(args):
    return build_and_upload_package_from_repo(
        path=args.path,
        upload=args.upload,
        skip_existing=args.skip_existing,
        package_name=args.package_name,
        all=args.all
    )


def add_deploy_subparser(subparsers):
    # deploy parser
    deploy_subparser = subparsers.add_parser('deploy', help='deploy a package')
    deploy_subparser.add_argument(
        '-u', '--upload', action='store_true', default=False, dest='upload')
    deploy_subparser.add_argument(
        '-p', '--path', action='store', default='./', dest='path')
    deploy_subparser.add_argument(
        '--skip', action='store_true', default=False, dest='skip_existing')
    deploy_subparser.add_argument(
        '-r', '--package_name', action='store')
    deploy_subparser.add_argument(
        '-a', '--all', action='store_true')
