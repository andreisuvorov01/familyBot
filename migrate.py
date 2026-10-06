"""
Применяет миграции Alembic (alembic upgrade head).
Существующие базы, созданные до появления Alembic, помечаются базовой ревизией автоматически.
DATABASE_URL должен указывать на PostgreSQL.
"""
import sys

from app.core.migrations import run_migrations

if __name__ == "__main__":
    try:
        run_migrations()
        print("Migrations completed successfully")
    except Exception as e:  # noqa: BLE001
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
