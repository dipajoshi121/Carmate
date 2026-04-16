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
    mig_dir = os.path.join(os.path.dirname(__file__), "migrations")
    sql_files = sorted(
        f for f in os.listdir(mig_dir) if f.endswith(".sql") and os.path.isfile(os.path.join(mig_dir, f))
    )
    if not sql_files:
        print(f"No .sql files in {mig_dir}")
        sys.exit(1)

    import psycopg2

    conn = psycopg2.connect(url)
    try:
        conn.autocommit = True
        total_st = 0
        with conn.cursor() as cur:
            for fname in sql_files:
                sql_path = os.path.join(mig_dir, fname)
                sql = open(sql_path, encoding="utf-8").read()
                statements = split_sql_statements(sql)
                if not statements:
                    print(f"Skip (no statements): {fname}")
                    continue
                print(f"Running {fname} ({len(statements)} statements)...")
                for i, stmt in enumerate(statements, 1):
                    try:
                        cur.execute(stmt)
                    except Exception as e:
                        print(f"  Statement {i} failed:\n{stmt[:200]}...\nError: {e}")
                        raise
                total_st += len(statements)
        print(f"Migration completed ({total_st} statements across {len(sql_files)} file(s)).")
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
