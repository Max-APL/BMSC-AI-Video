import sqlite3
import os

db_path = os.path.join("storage", "metadata.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN role_id VARCHAR")
        conn.commit()
        print("Migración completada con éxito.")
    except Exception as e:
        print(f"Error o ya migrado: {e}")
    conn.close()
else:
    print("No database found.")
