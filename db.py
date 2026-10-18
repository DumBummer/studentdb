import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

@contextmanager
def get_db():
    url = os.getenv('DATABASE_URL')
    if url:
        conn = psycopg.connect(url, row_factory=dict_row)
    else:
        conn = psycopg.connect(host=os.getenv('DB_HOST','localhost'), port=os.getenv('DB_PORT','5432'), dbname=os.getenv('DB_NAME','studentdb'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD',''), row_factory=dict_row)
    try:
        with conn:
            yield conn
    finally:
        conn.close()
