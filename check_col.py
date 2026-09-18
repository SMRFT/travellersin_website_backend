
import sqlite3
import os

db_path = 'db.sqlite3'
if not os.path.exists(db_path):
    print("DB not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("PRAGMA table_info(Travellersin_website_backend_booking)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'discount_amount' in columns:
        print("EXISTS")
    else:
        print("MISSING")
except Exception as e:
    print(f"Error: {e}")
conn.close()
