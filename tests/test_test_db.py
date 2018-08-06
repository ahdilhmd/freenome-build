import os
import subprocess

import pytest

from freenome_build.db import (
    start_local_database,
    start_k8s_database,
    setup_db,
    insert_test_data,
    reset_data,
    stop_local_database,
    stop_k8s_database,
    DbConnectionData
)
from freenome_build.util import run_and_log

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "./skeleton_repo/"))


@pytest.mark.skipif('TRAVIS' not in os.environ,
                    reason="Test for travis where the database is created by the postgresql service")
def test_travis_db_cli():
    conn_string = "postgresql://freenome_build:password@localhost:5432/freenome_build"
    connect_cmd = f"psql {conn_string}"
    conn_data = DbConnectionData.from_conn_string(conn_string)

    setup_db(conn_data, DB_DIR)

    insert_test_data(conn_data, DB_DIR)
    stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
    assert stdout == "test \n------\n test\n(1 row)"

    reset_data(conn_data, DB_DIR)
    stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
    assert stdout == "test \n------\n(0 rows)"

    insert_test_data(conn_data, DB_DIR)
    stdout = subprocess.check_output(connect_cmd, shell=True, input=b"SELECT * FROM test; \q").decode().strip()
    assert stdout == "test \n------\n test\n(1 row)"


def test_docker_db_cli():
    """Check that we can start, connect to, and stop a test db."""
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
        stop_cmd = f"freenome-build db --conn-string {conn_string} stop-local"
        subprocess.check_call(stop_cmd, shell=True)


def test_db_module_interface():
    conn_data = start_local_database(DB_DIR, 'freenome_build')
    setup_db(conn_data, DB_DIR)
    insert_test_data(conn_data, DB_DIR)
    reset_data(conn_data, DB_DIR)
    stop_local_database(conn_data)


def _test_k8s_connection(testing_pod_id: str, conn_data: DbConnectionData):
    # Try connecting with our new connection. pg_isready doesn't take connection
    # strings so we need to take it apart a little.
    run_and_log(f"kubectl exec {testing_pod_id} -- pg_isready -h {conn_data.host} "
                f"-p {conn_data.port} -U {conn_data.user} -d {conn_data.dbname}")


# TODO(travis_service_account)
@pytest.mark.skip(reason="There's no google service account for travis yet")
def test_k8s_db_cli():
    try:
        start_cmd = f"freenome-build db start-k8s"
        start_response = subprocess.check_output(start_cmd, shell=True).decode().strip().split("\n")
        conn_data1 = DbConnectionData.from_conn_string(start_response[0])

        start_response = subprocess.check_output(start_cmd, shell=True).decode().strip().split("\n")
        conn_data2 = DbConnectionData.from_conn_string(start_response[0])
        pod_id2 = start_response[1]

        # Modify our connection data so that we can get a new connection string with
        # postgres as the user and database. We need to do this since the database doesn't
        # have the user and database created yet.
        conn_data1.user = 'postgres'
        conn_data1.dbname = 'postgres'
        _test_k8s_connection(pod_id2, conn_data1)
    finally:
        # Try stopping the database using their IPs instead of pod_ids
        stop_cmd = f"freenome-build db --host {conn_data1.host} stop-k8s"
        run_and_log(stop_cmd)
        stop_cmd = f"freenome-build db --conn-string {conn_data2} stop-k8s"
        run_and_log(stop_cmd)
 

# TODO(travis_service_account)
@pytest.mark.skip(reason="There's no google service account for travis yet")
def test_k8s_db_interface():
    try:
        conn_data, pod_id1 = start_k8s_database(DB_DIR, 'freenome_build')
        # Start a second container and see if we can communicate with the original one.
        _, pod_id2 = start_k8s_database(DB_DIR, 'freenome_build')
        # Modify our connection data so that we can get a new connection string with
        # postgres as the user and database. We need to do this since the database doesn't
        # have the user and database created yet.
        conn_data.user = 'postgres'
        conn_data.dbname = 'postgres'
        _test_k8s_connection(pod_id2, conn_data)
    finally:
        stop_k8s_database(pod_id1)
        stop_k8s_database(pod_id2)
