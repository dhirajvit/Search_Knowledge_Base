import json
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url():
    """Build database URL from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    password_secret_arn = os.getenv("DB_PASSWORD_SECRET_ARN")
    if password_secret_arn:
        import boto3

        region = os.getenv("DEFAULT_AWS_REGION", "ap-southeast-2")
        client = boto3.client("secretsmanager", region_name=region)
        secret = json.loads(
            client.get_secret_value(SecretId=password_secret_arn)["SecretString"]
        )
        password = secret["password"]
    else:
        password = os.getenv("DB_PASSWORD", "")

    host = os.getenv("RDS_ENDPOINT", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "searchknowledgebase")
    user = os.getenv("DB_USER", "dbadmin")

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def run_migrations_offline():
    url = get_database_url()
    context.configure(url=url, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
