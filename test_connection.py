
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

try:
    with psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname="postgres",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD")
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT datname, length(datname)
                FROM pg_database
                ORDER BY datname
            """)

            for name, length in cur.fetchall():
                print(f"Database: {name!r} | Length: {length}")

except psycopg.Error as error:
    print("Database error:", error)
