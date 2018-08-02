import logging
import os
import random
import socket
import subprocess
import string
import time

import psycopg2
from contextlib import closing
from urllib.parse import urlparse

from freenome_build.util import norm_abs_join_path, change_directory, get_git_repo_name, run_and_log

logger = logging.getLogger(__file__)  # noqa: invalid-name

# the maximum amount of time in seconds to wait for the DB to come up before raising an error
MAX_DB_WAIT_TIME = 10


class ConnectionData():
    def __init__(self, host, port, dbname, user, password=None):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.conn = None

    @classmethod
    def from_conn_string(cls, conn_string):
        parsed = urlparse(conn_string)
        return cls(parsed.hostname, parsed.port, parsed.path[1:], parsed.username, parsed.password)

    @property
    def conn_string(self):
        out = f"postgresql://{self.user}"
        if self.password:
            out += f":{self.password}"
        out += f"@{self.host}:{self.port}/{self.dbname}"
        return out

    @property
    def sqitch_string(self):
        out = f"db:pg://{self.user}"
        if self.password:
            out += f":{self.password}"
        out += f"@{self.host}:{self.port}/{self.dbname}"
        return out

    def __str__(self):
        return self.conn_string


class ContainerDoesNotExistError(Exception):
    pass


def _execute_sql_script(sql_script_path, dbuser, dbname, host, port):
    pass


def _find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def setup_db(conn_data: ConnectionData, repo_path: str) -> None:
    # check if 'setup' exists in repo_path/database/
    repo_setup_sql_path = norm_abs_join_path(repo_path, "./database/setup.sql")
    if os.path.exists(repo_setup_sql_path):
        with open(repo_setup_sql_path) as ifp:
            setup_sql = ifp.read()
    # if this doesn't exist, revert to the default
    else:
        setup_sql_template_path = norm_abs_join_path(
            os.path.dirname(__file__), "./database_template/scripts/setup.sql")
        logger.debug(f"The repo at '{repo_path}' does not contain './database/setup.sql'."
                     f"\nDefaulting to {setup_sql_template_path} with "
                     f"USER='{conn_data.user}', DATABASE='{conn_data.dbname}', "
                     f"PASSWORD='{conn_data.password}")
        with open(setup_sql_template_path) as ifp:
            setup_sql = ifp.read().format(
                PGUSER=conn_data.user, PGDATABASE=conn_data.dbname, PGPASSWORD=conn_data.password
            )
    logger.info(setup_sql)
    run_and_log(f"psql -h {conn_data.host} -p {conn_data.port} -U postgres -d postgres",
                input=setup_sql.encode())
    _run_migrations(conn_data, repo_path)


def start_local_database(repo_path: str, project_name: str, port: int = None, password: str = None) -> ConnectionData:
    """Start a test database in a docker container.

    This starts a new test database in a docker container. This function:
    1) builds the postgres server docker image
    2) starts the docker container on port 'port'
    """
    # The default dbname and user are the project_name. We'll also generate a random
    # password if one wasn't passed in.
    dbname = project_name
    user = project_name

    # set the path to the Postgres Dockerfile
    docker_file_path = norm_abs_join_path(repo_path, "./database/Dockerfile")
    # if the repo doesn't have a Dockerfile in the database sub-directory, then
    # default to the template Dockerfile
    if not os.path.exists(docker_file_path):
        docker_file_path = norm_abs_join_path(
            os.path.dirname(__file__), "./database_template/Dockerfile")
        logger.info(f"Setting DB docker file path to '{docker_file_path}'")

    docker_file_dir = os.path.dirname(docker_file_path)

    # build
    build_cmd = f"docker build --rm -t {dbname}:latest {docker_file_dir}"
    run_and_log(build_cmd)

    # Find a free port if one wasn't specified
    if port is None:
        port = _find_free_port()
    if password is None:
        password = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(32)])

    # starting db
    run_cmd = f"docker run -d -p {port}:5432 --name {dbname}_{port} {dbname}:latest"
    run_and_log(run_cmd)

    # Get the IP automatically
    host = socket.gethostbyname(socket.gethostname())
    # Wait for the db to start up before configuring it
    _wait_for_db_cluster_to_start(host, port)

    conn_data = ConnectionData(host, port, dbname, user, password)

    return conn_data


def _run_migrations(conn_data: ConnectionData, repo_path: str) -> None:
    # check if 'migrate' exists in repo_path/database/
    repo_migrate_path = norm_abs_join_path(repo_path, "./database/migrate")
    if os.path.exists(repo_migrate_path):
        # If it does, run the migration script
        run_and_log(repo_migrate_path)
        return
    logger.info(f"The repo at '{repo_path}' does not contain './database/migrate' script"
                "\nDefaulting to running sqitch migrations in './database/sqitch'")
    sqitch_path = norm_abs_join_path(repo_path, "./database/sqitch")
    if not os.path.exists(sqitch_path):
        raise RuntimeError(
            f"Sqitch migration files must exist at '{sqitch_path}' "
            "if a migration script is not provided.")

    with change_directory(sqitch_path):
        try:
            run_and_log(
                f"sqitch --engine pg deploy {conn_data.sqitch_string}")
        except subprocess.CalledProcessError as inst:
            # we don't care if there's nothing to deploy
            if inst.stderr.decode().strip() == 'Nothing to deploy (empty plan)':
                pass
            else:
                raise


def insert_test_data(conn_data: ConnectionData, repo_path: str) -> None:
    # check if 'insert_test_data' exists in repo_path/database/
    repo_insert_test_data_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data")
    if os.path.exists(repo_insert_test_data_path):
        run_and_log(repo_insert_test_data_path)
        return
    logger.debug(
        f"The repo at '{repo_path}' does not contain './database/insert_test_data' script")

    repo_insert_test_data_sql_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data.sql")
    if os.path.exists(repo_insert_test_data_sql_path):
        logger.info(f"Inserting data in '{repo_insert_test_data_sql_path}'.")
        with open(repo_insert_test_data_sql_path) as ifp:
            run_and_log(
                f"psql {conn_data.conn_string}",
                input=ifp.read().encode()
            )
        return
    else:
        logger.info(
            f"The repo at '{repo_path}' does not contain './database/insert_test_data.sql' script")

    raise ValueError(f"'{repo_path}' does not contain an insert test data script or sql file.")


def _wait_for_db_cluster_to_start(host: str, port: int, max_wait_time=MAX_DB_WAIT_TIME, recheck_interval=0.2) -> None:
    conn_str = f"dbname=postgres user=postgres host={host} port={port}"
    for _ in range(int(max_wait_time/recheck_interval)+1):
        try:
            with psycopg2.connect(conn_str) as _: # noqa
                # we just want to see if we can connect, so if we do then connect
                logger.debug(f"Database at '{host}:{port}' is up!")
                return
        except psycopg2.OperationalError:
            logger.debug(f"DB cluster at '{host}:{port}' is not yet up.")
            time.sleep(recheck_interval)
            continue

    raise RuntimeError(f"Aborting because the DB did not start within {MAX_DB_WAIT_TIME} seconds.")


def reset_data(conn_data: ConnectionData, repo_path: str) -> None:
    repo_reset_data_path = norm_abs_join_path(
        repo_path, "./database/reset_data")
    repo_reset_data_sql_path = norm_abs_join_path(
        repo_path, "./database/reset_data.sql")
    # Check if 'reset_data' exists in repo_path/database/
    if os.path.exists(repo_reset_data_path):
        run_and_log(repo_reset_data_path)
    # Check if 'reset_data.sql' exists in repo_path/database
    elif os.path.exists(repo_reset_data_path):
        run_and_log(repo_reset_data_path)
        with open(repo_reset_data_sql_path) as ifp:
            run_and_log(
                f"psql {conn_data.conn_string}",
                input=ifp.read().encode()
            )
    else:
        # Drop the database
        run_and_log(f"psql -h {conn_data.host} -p {conn_data.port} -U postgres -d postgres",
                    input=f"drop database {conn_data.dbname}")
        # Drop the user
        run_and_log(f"psql -h {conn_data.host} -p {conn_data.port} -U postgres -d postgres",
                    input=f"drop user {conn_data.user}")
        # Recreate the database and run migrations
        setup_db(conn_data, repo_path)


def stop_local_database(conn_data: ConnectionData) -> None:
    image_name = f"{conn_data.dbname}_{conn_data.port}"
    cmd = f"docker kill {image_name}"
    try:
        run_and_log(cmd)
    except subprocess.CalledProcessError as inst:
        # if this is an error because the container already exists, then raise
        # a custom error type
        pat = (f"Error response from daemon: Cannot kill container:"
               f" {image_name}: No such container: {image_name}")
        if inst.stderr.decode().strip() == pat:
            raise ContainerDoesNotExistError(inst)
        # otherwise just propogate the error
        else:
            raise

    cmd = f"docker rm -f {image_name}"
    run_and_log(cmd)


def start_local_database_main(args):
    conn_data = start_local_database(args.path, args.project_name, port=args.port)
    logger.info(f"Successfully started a database. Use the following string to connect:")
    print(conn_data)


def start_local_test_database_main(args):
    if args.conn_data:
        conn_data = start_local_database(args.path, args.conn_data.dbname,
                                         port=args.conn_data.port, password=args.conn_data.password)
    else:
        conn_data = start_local_database(args.path, args.project_name, port=args.port)
    setup_db(conn_data, args.path)
    insert_test_data(conn_data, args.path)
    logger.info(f"Successfully started a database. Use the following string to connect:")
    print(conn_data)


def setup_db_main(args):
    if not args.conn_data:
        args.conn_data = ConnectionData(args.host, args.port, args.project_name, args.project_name, args.password)
    setup_db(args.conn_data, args.path)


def insert_test_data_main(args):
    if not args.conn_data:
        args.conn_data = ConnectionData(args.host, args.port, args.project_name, args.project_name, args.password)
    insert_test_data(args.conn_data, args.path)


def reset_data_main(args):
    if not args.conn_data:
        args.conn_data = ConnectionData(args.host, args.port, args.project_name, args.project_name, args.password)
    reset_data(args.conn_data, args.path)


def stop_local_database_main(args):
    if not args.conn_data:
        args.conn_data = ConnectionData(args.host, args.port, args.project_name, args.project_name, args.password)
    stop_local_database(args.conn_data)


def add_db_subparser(subparsers):
    database_parser = subparsers.add_parser('db', help='manage the test database')
    database_parser.required = True
    database_parser.add_argument('--path', default='.')
    database_parser.add_argument(
        '--port', type=int,
        help='Port on which to start the test db. Default is a random free port'
    )
    database_parser.add_argument(
        '--host', default='localhost',
        help='Test DB host. Default: %(default)s'
    )
    database_parser.add_argument(
        '--password', default=None,
        help='Test DB port. Autogenerated by default'
    )
    database_parser.add_argument(
        '--project-name',
        default=None,
        help='The name of the project.\n'
             'This is assumed to be the name of the database and the database owner.\n'
             'Default: The name of the git repo at $PATH with - replaced with _'
    )
    database_parser.add_argument(
        '--conn-string', default=None,
        help='The postgres connection string that can be used to connect to the db'
    )

    # add the subparsers
    database_subparsers = database_parser.add_subparsers(dest='test_db_command')
    database_subparsers.required = True

    # Start a DB
    database_subparsers.add_parser('start', help='Start a database')

    # Start a test DB, run migrations, insert the starting data
    database_subparsers.add_parser('start-local-test-db', help='Start a database with all the default data')

    # Run the sqitch migrations on the database
    database_subparsers.add_parser('setup-db', help='Create database and run migrations on database schemas')

    # Insert test data into the database
    database_subparsers.add_parser('insert-test-data', help='Insert test data into the database')

    # Reset the database to its starting point.
    database_subparsers.add_parser('reset-data',
                                   help='Reset the data in the database.'
                                   'Requires inserting the test data afterwards.')

    # Stop the test db
    database_subparsers.add_parser('stop', help='stop the test database')


def db_main(args):
    # normalize the path
    args.path = norm_abs_join_path(args.path)

    # set the project name to the name of the git repo at args.path
    if args.project_name is None:
        args.project_name = get_git_repo_name(args.path).replace('-', '_')
        logger.info(f"Setting project name to '{args.project_name}'")

    if args.conn_string is not None:
        args.conn_data = ConnectionData.from_conn_string(args.conn_string)
    else:
        args.conn_data = None

    if args.test_db_command == 'start':
        start_local_database_main(args)
    elif args.test_db_command == 'start-local-test-db':
        start_local_test_database_main(args)
    elif args.test_db_command == 'setup-db':
        setup_db_main(args)
    elif args.test_db_command == 'insert-test-data':
        insert_test_data_main(args)
    elif args.test_db_command == 'reset-data':
        reset_data_main(args)
    elif args.test_db_command == 'stop':
        stop_local_database_main(args)
    else:
        raise ValueError(f"Unrecognized DB subcommand '{args.test_db_command}'")
