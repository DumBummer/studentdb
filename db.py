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
        conn = psycopg.connect(host=os.getenv('DB_HOST','127.0.0.1'), port=os.getenv('DB_PORT','5433'), dbname=os.getenv('DB_NAME','CATUBIG_CSPC103'), user=os.getenv('DB_USER','studentdb_user'), password=os.getenv('DB_PASSWORD','0005'), row_factory=dict_row)
    try:
        with conn:
            yield conn
    finally:
        conn.close()
