from flask_sqlalchemy import SQLAlchemy
import os


#postgresql://username:password@hostname:port/database_name
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres:5432/{os.getenv('POSTGRES_DB')}"
)

#sql alchemy instance
db = SQLAlchemy()