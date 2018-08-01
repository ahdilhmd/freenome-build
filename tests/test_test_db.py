import os
import subprocess

import pytest

from freenome_build.db import (
    start_local_database,
    setup_db,
    insert_test_data,
    reset_data,
    stop_local_database
)
from freenome_build.util import run_and_log

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "./skeleton_repo/"))


@pytest.mark.skipif('TRAVIS' not in os.environ,
                    reason="Test for travis where the database is created by the postgresql service")
def test_travis_db_cli():
    """Check that we can start, connect to, and stop a test db."""
    initial_wd = os.getcwd()
    os.chdir(DB_DIR)
    try:
        base_conn_string = "postgresql://postgres@localhost:5432"
        run_and_log(f"psql {base_conn_string}", input="CREATE DATABASE freenome_build WITH OWNER=postgres")
        conn_string = f"{base_conn_string}/freenome_build"
        connect_cmd = f"psql {conn_string}"

        setup_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} setup-db"
        subprocess.check_call(setup_cmd, shell=True)

        insert_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} insert-test-data"
        subprocess.check_output(insert_cmd, shell=True).decode().strip()
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n test\n(1 row)"

        reset_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} reset-data"
        subprocess.check_output(reset_cmd, shell=True).decode().strip()
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n(0 rows)"

        insert_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} insert-test-data"
        subprocess.check_output(insert_cmd, shell=True).decode().strip()
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n test\n(1 row)"
    finally:
        os.chdir(initial_wd)


def test_docker_db_cli():
    """Check that we can start, connect to, and stop a test db."""
    initial_wd = os.getcwd()
    os.chdir(DB_DIR)
    try:
        start_cmd = f"freenome-build db --path {DB_DIR} start-local-test-db"
        conn_string = subprocess.check_output(start_cmd, shell=True).decode().strip()
        connect_cmd = f"psql {conn_string}"
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n test\n(1 row)"

        reset_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} reset-data"
        subprocess.check_output(reset_cmd, shell=True).decode().strip()
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n(0 rows)"

        insert_cmd = f"freenome-build db --path {DB_DIR} --conn-string {conn_string} insert-test-data"
        subprocess.check_output(insert_cmd, shell=True).decode().strip()
        stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
        assert stdout == "test \n------\n test\n(1 row)"
    finally:
        os.chdir(initial_wd)
        stop_cmd = f"freenome-build db --conn-string {conn_string} stop"
        subprocess.check_call(stop_cmd, shell=True)


def test_db_module_interface():
    conn_data = start_local_database(DB_DIR, 'freenome_build')
    setup_db(conn_data, DB_DIR)
    insert_test_data(conn_data, DB_DIR)
    reset_data(conn_data, DB_DIR)
    stop_local_database(conn_data)
