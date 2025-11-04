import os

# Configure pytest-postgresql to use mise-installed system Postgres
os.environ.setdefault("POSTGRESQL_HOST", "localhost")
os.environ.setdefault("POSTGRESQL_PORT", "5432")
os.environ.setdefault("POSTGRESQL_USER", "postgres")
os.environ.setdefault("POSTGRESQL_PASSWORD", "")
os.environ.setdefault("POSTGRESQL_DBNAME", "postgres")
os.environ.setdefault("POSTGRESQL_CONNECTION_TYPE", "psycopg")
