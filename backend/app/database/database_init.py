import json
import os

import boto3
import psycopg2
from alembic import command
from alembic.config import Config


def run_migrations():
    try:
        alembic_ini = os.path.join(os.path.dirname(__file__), "..", "database", "alembic.ini")
        alembic_cfg = Config(alembic_ini)
        command.upgrade(alembic_cfg, "head")
        print("Migrations completed successfully.")
    except Exception as e:
        print(f"Migration warning: {e}")


def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    password_secret_arn = os.getenv("DB_PASSWORD_SECRET_ARN")
    if password_secret_arn:
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


def get_db_connection():
    return psycopg2.connect(get_database_url())
