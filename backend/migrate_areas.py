import sqlite3
import os
import json

db_path = os.path.join("storage", "metadata.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE roles ADD COLUMN allowed_areas VARCHAR")
        conn.commit()
        print("Migración completada con éxito. Se añadió 'allowed_areas'.")
        
        # Set all existing roles to have access to all areas by default so we don't break existing ones
        all_areas_json = json.dumps(["*"])
        c.execute("UPDATE roles SET allowed_areas = ?", (all_areas_json,))
        conn.commit()
        print("Roles existentes actualizados con acceso a todas las áreas.")
    except Exception as e:
        print(f"Error o ya migrado: {e}")
    conn.close()
else:
    print("No database found.")
