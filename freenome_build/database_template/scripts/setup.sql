CREATE ROLE {PGUSER};
ALTER ROLE {PGUSER}
    WITH NOSUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS
    PASSWORD '{PGPASSWORD}';
CREATE DATABASE {PGDATABASE} WITH OWNER={PGUSER};
