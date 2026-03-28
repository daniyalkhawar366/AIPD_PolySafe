import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'polysafe.db')

def get_connection():
    """Create a database connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """Initialize the database with the medications table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            drug_name TEXT,
            rxcui TEXT,
            date_added TEXT,
            source TEXT
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
