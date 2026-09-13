import psycopg2
from psycopg2 import sql

from server.config import Settings

def init_db():
    settings = Settings()
    connection_params = {
        "host": "localhost",
        "port": settings.db_port,
        "user": settings.db_user,
        "password": settings.db_password,
        "dbname": "postgres"
    }

    server_db_name = settings.db_name

if __name__ == "__main__":
    init_db()
