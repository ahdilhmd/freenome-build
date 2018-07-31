import logging
import os
import psycopg2
import socket
import subprocess
import time
from typing import Tuple
from contextlib import closing

from freenome_build.util import norm_abs_join_path, change_directory, get_git_repo_name, run_and_log

logger = logging.getLogger(__file__)  # noqa: invalid-name

# the maximum amount of time in seconds to wait for the DB to come up before raising an error
MAX_DB_WAIT_TIME = 10


class ContainerDoesNotExistError(Exception):
    pass


def _execute_sql_script(sql_script_path, dbuser, dbname, host, port):
    pass


def _find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def _setup_db(repo_path: str, host: str, port: int, project_name: str = None) -> None:
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
                     f"USER='{project_name}', DATABASE='{project_name}'")
        # get the new database password from the environment
        password_env_var = f"{project_name}_DB_PASSWORD"
        if password_env_var not in os.environ:
            raise ValueError(f"{password_env_var} must be in the environment to setup a new database.")
        with open(setup_sql_template_path) as ifp:
            setup_sql = ifp.read().format(
                PGUSER=project_name, PGDATABASE=project_name, PGPASSWORD=os.environ[password_env_var]
            )

    # execute the setup.sql script
    run_and_log(f"psql -h {host} -p {port} -U postgres -d postgres", input=setup_sql.encode())

    return


def _wait_for_db_cluster_to_start(host: str, port: int, max_wait_time=MAX_DB_WAIT_TIME, recheck_interval=0.2) -> None:
    conn_str = f"dbname=postgres user=postgres host={host} port={port}"
    for _ in range(int(max_wait_time/recheck_interval)+1):
        try:
            with psycopg2.connect(conn_str) as _: # noqa
                # we just want to see if we can connect, so if we do then connect
                logger.debug(f"Database at '{conn_str}' is up!")
                return
        except psycopg2.OperationalError:
            logger.debug(f"DB cluster at '{conn_str}' is not yet up.")
            time.sleep(recheck_interval)
            continue

    raise RuntimeError(f"Aborting because the DB did not start within {MAX_DB_WAIT_TIME} seconds.")


def start_local_database(repo_path: str, project_name: str, port: int = None) -> Tuple[str, int]:
    """Start a test database in a docker container.

    This starts a new test database in a docker container. This function:
    1) builds the postgres server docker image
    2) starts the docker container on port 'port'
    """
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
    build_cmd = f"docker build --rm -t {project_name}:latest {docker_file_dir}"
    run_and_log(build_cmd)

    # Find a free port if one wasn't specified
    if port is None:
        port = _find_free_port()
    # starting db
    run_cmd = f"docker run -d -p {port}:5432 --name {project_name}_{port} {project_name}:latest"
    run_and_log(run_cmd)

    # Wait for the db to start up before configuring it
    _wait_for_db_cluster_to_start('localhost', port)

    try:
        # Set up the database
        _setup_db(repo_path, 'localhost', port, project_name)

        # Try connecting to the new database
        connection_str = f"host=localhost port={port} user={project_name} dbname={project_name}"
        return connection_str, port
    except Exception:
        stop_local_database(project_name, port)
        raise


def run_migrations(repo_path: str, host: str, port: int, dbname: str, dbuser: str) -> None:
    # check if 'migrate' exists in repo_path/database/
    repo_migrate_path = norm_abs_join_path(repo_path, "./database/migrate")
    if os.path.exists(repo_migrate_path):
        # TODO -- add support for running this script
        raise NotImplementedError("We have not implemented running migrate from the repo.")

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
                f"sqitch --engine pg deploy db:pg://postgres@{host}:{port}/{dbname}")
        except subprocess.CalledProcessError as inst:
            # we don't care if there's nothing to deploy
            if inst.stderr.decode().strip() == 'Nothing to deploy (empty plan)':
                pass
            else:
                raise
    return


def insert_test_data(repo_path: str, host: str, port: str, dbuser: str, dbname: str) -> None:
    # check if 'insert_test_data' exists in repo_path/database/
    repo_insert_test_data_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data")
    if os.path.exists(repo_insert_test_data_path):
        # TODO -- add support for running this script
        raise NotImplementedError("We have not implemented running insert_test_data from the repo.")
    else:
        logger.debug(
            f"The repo at '{repo_path}' does not contain './database/insert_test_data' script")

    repo_insert_test_data_sql_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data.sql")
    if os.path.exists(repo_insert_test_data_sql_path):
        logger.info(f"Inserting data in '{repo_insert_test_data_sql_path}'.")
        with open(repo_insert_test_data_sql_path) as ifp:
            run_and_log(
                f"psql -h {host} -p {port} -U {dbuser} {dbname}",
                input=ifp.read().encode()
            )
        return
    else:
        logger.info(
            f"The repo at '{repo_path}' does not contain './database/insert_test_data.sql' script")

    raise ValueError(f"'{repo_path}' does not contain an insert test data script or sql file.")


def reset_test_data(host: str, port: str, user: str, dbname: str) -> None:
    conn = psycopg2.connect(host=host, port=port, user=user, dbname=dbname)
    cursor = conn.cursor()
    # Select the namespace and the tablename ignoring any tables that start
    # with pg_ and sql_ and any sqitch namespaces
    get_all_tables_sql = "select nspname||'.'||relname from pg_class join pg_namespace on " \
                         "relnamespace = pg_namespace.oid where relkind='r' and " \
                         "relname !~ '^(pg_|sql_)' and nspname != 'sqitch';"
    cursor.execute(get_all_tables_sql)
    tables = cursor.fetchall()
    for table in tables:
        cursor.execute(f'delete from {table[0]}')


def stop_local_database(project_name: str, port: int) -> None:
    image_name = f"{project_name}_{port}"
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
    connection_str, port = start_local_database(args.path, args.project_name, args.port)
    logger.info(f"Successfully started a database. Use the following string to connect:\n{connection_str}")


def start_local_test_database_main(args):
    connection_str, port = start_local_database(args.path, args.project_name, args.port)
    run_migrations(args.path, args.host, port, args.project_name, args.project_name)
    insert_test_data(args.path, args.host, port, args.project_name, args.project_name)
    logger.info(f"Successfully started a database. Use the following string to connect:\n{connection_str}")


def run_migrations_main(args):
    run_migrations(args.path, args.host, args.port, args.project_name, args.project_name)


def insert_test_data_main(args):
    insert_test_data(args.path, args.host, args.port, args.project_name, args.project_name)


def reset_test_data_main(args):
    reset_test_data(args.host, args.port, args.project_name, args.project_name)


def stop_local_database_main(args):
    stop_local_database(args.project_name, args.port)


def add_db_subparser(subparsers):
    database_parser = subparsers.add_parser('db', help='manage the test database')
    database_parser.required = True
    database_parser.add_argument('--path', default='.')
    database_parser.add_argument(
        '--port',
        help='Port on which to start the test db. Default is a random free port'
    )
    database_parser.add_argument(
        '--host', default='localhost',
        help='Teste DB host. Default: %(default)s'
    )
    database_parser.add_argument(
        '--project_name',
        default=None,
        help='The name of the project.\n'
             'This is assumed to be the name of the database and the database owner.\n'
             'Default: The name of the git repo at $PATH with - replaced with _'
    )

    # add the subparsers
    database_subparsers = database_parser.add_subparsers(dest='test_db_command')
    database_subparsers.required = True

    # Start a DB
    database_subparsers.add_parser('start', help='Start a database')

    # Start a test DB, run migrations, insert the starting data
    database_subparsers.add_parser('start_local_test_db', help='Start a database with all the default data')

    # Run the sqitch migrations on the database
    database_subparsers.add_parser('run_migrations', help='Run migrations on database schemas')

    # Insert test data into the database
    database_subparsers.add_parser('insert_test_data', help='Insert test data into the database')

    # Reset the database to its starting point.
    database_subparsers.add_parser('reset_test_data',
                                   help='Reset the data in the test database.'
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

    if args.test_db_command == 'start':
        start_local_database_main(args)
    elif args.test_db_command == 'start_local_test_db':
        start_local_test_database_main(args)
    elif args.test_db_command == 'run_migrations':
        run_migrations_main(args)
    elif args.test_db_command == 'insert_test_data':
        insert_test_data_main(args)
    elif args.test_db_command == 'reset_test_data':
        reset_test_data_main(args)
    elif args.test_db_command == 'stop':
        stop_local_database_main(args)
    else:
        raise ValueError(f"Unrecognized DB subcommand '{args.test_db_command}'")
