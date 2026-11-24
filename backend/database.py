import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import URL


db = SQLAlchemy()


def database_url():
    return os.getenv("DATABASE_URL") or URL.create(
        "postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="postgres",
        port=5432,
        database=os.getenv("POSTGRES_DB"),
    )
