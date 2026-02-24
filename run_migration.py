"""
Run once to create/update Neon schema: set DATABASE_URL then run
  python run_migration.py
"""
import os
import sys

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Set DATABASE_URL and run again.")
        sys.exit(1)
    sql_path = os.path.join(os.path.dirname(__file__), "migrations", "001_schema.sql")
    if not os.path.isfile(sql_path):
        print(f"Migration file not found: {sql_path}")
        sys.exit(1)
    sql = open(sql_path, encoding="utf-8").read()
    import psycopg2
    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
        print("Migration completed.")
    except Exception as e:
        print("Migration failed:", e)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
