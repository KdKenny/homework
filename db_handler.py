import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_Config = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', 5432),
}

def connect_db():
    """Establish a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_Config)
        return conn
    except Exception as e:
        print( f"無法連接到數據庫 : {e}")
        return None