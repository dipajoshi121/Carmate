"""
Run to create/update Neon/Postgres schema. Set DATABASE_URL (in .env or env) then:
  python run_migration.py

Executes each SQL statement separately (psycopg2 ignores everything after the first
statement in a single execute(), which previously left columns like users.role missing).
"""
import os
import sys
from pathlib import Path

# Load .env from project root so DATABASE_URL is available
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass


def split_sql_statements(sql: str) -> list[str]:
    """Split migration file into executable statements; strip line comments."""
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    text = "\n".join(lines)
    statements = []
    for chunk in text.split(";"):
        s = chunk.strip()
        if s:
            statements.append(s)
    return statements


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
    statements = split_sql_statements(sql)
    if not statements:
        print("No SQL statements found in migration file.")
        sys.exit(1)

    import psycopg2

    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for i, stmt in enumerate(statements, 1):
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f"Statement {i} failed:\n{stmt[:200]}...\nError: {e}")
                    raise
        print(f"Migration completed ({len(statements)} statements).")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'role'
                """
            )
            if cur.fetchone():
                print("Verified: users.role column exists.")
            else:
                print("Warning: users.role not found after migration.")
    except Exception as e:
        print("Migration failed:", e)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
