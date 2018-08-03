# Database Template

## Local testing Database

### Quick Start

Start a local test database
```
freenome-build db start
```

Start a test database, run migrations, and insert test data
```
freenome-build db start-local-test-db
```

Create the database in the started postgres service, create users, and run migrations.
By default, it will create a user and database with the values specified in the connection string
```
freenome-build db --conn-string postgresql://{dbuser}:{password}@{host}:{port}/{dbname} setup-db
```

Stop a test database
```
freenome-build db --conn-string postgresql://{dbuser}:{password}@{host}:{port}/{dbname} stop
```

Insert test data into the test database
```
freenome-build db --conn-string postgresql://{dbuser}:{password}@{host}:{port}/{dbname} insert-test-data
```

Reset the data inside the test database (Does not require rerunning migrations)
```
freenome-build db --conn-string postgresql://{dbuser}:{password}@{host}:{port}/{dbname} reset-data
```

### Database Management Template Scripts

There are 3 basic commands that need to be run to use the testing database. We need to be able to initialize the database with the correct structure, insert test data, and drop test data. This directory contains default scripts that perform these actions, and serve both as a sensible default and a template if more control is needed.

#### Database Setup
Initialize a database. This is where extensions should be loaded, users should be added, permissions should be set, and migrations should be run.

This attempts to execute the following scripts in this order:
1) run `$REPO/database/setup.sql` as the DB owner
2) `setup.sql` from `database_template/scripts/` in this repo

Database migrations:
1) Run `$REPO/database/migrate`
2) run `sqitch --engine pg deploy db:pg://{dbuser}:{password}@{host}:{port}/{dbname}` from `$REPO/database/sqitch`

The postgres connection URI will be returned to stdout

The following command will start the database and in addition, run the migrations and insert test data.
```
freenome-build db start-local-test-db
```

#### Test Data Insertion
This inserts the test data into the database. Note that this does *not* reset the data first. In a real test script, you need to reset the database and then insert the test data.

This attempts to execute the following scripts in this order:
1) execute `$REPO/database/insert_test_data`
2) run `$REPO/database/insert_test_data.sql` as the DB owner

#### Database Reset
This should remove all non-migration data from the database.

This attempts to execute the database setup scripts in the following order:
1) `$REPO/database/reset_data` in `$DATABASE_SETUP_SCRIPTS`
2) run `$REPO/database/reset_data.sql` as the database owner
3) Drop the database in the connection string and rerun setup and migrations.

**Note: The speed of this could be significantly increased by creating a template database the first time, and reloading from the template in subsequent resets.**
