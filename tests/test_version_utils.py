import os.path

import freenome_build.version_utils


def test_get_version():
    test_path = os.path.dirname(os.path.realpath(__file__))
    path = os.path.abspath(os.path.join(test_path, '..'))
    vsn = freenome_build.version_utils.get_version_from_setup_py(path)
    assert vsn.count(b'.') == 2
    # want to test something about the version string - just fix the test if we
    # release version 3.
    assert chr(vsn[0]) == '2'
