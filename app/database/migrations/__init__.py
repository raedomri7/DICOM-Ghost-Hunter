"""Database migrations placeholder.

Schema versioning is handled by SQLAlchemy `create_all` for the MVP. A future
PostgreSQL migration can adopt Alembic; this file documents the migration path
and reserves the migrations directory.

Migration strategy:
1. v1 (current): declarative Base.metadata.create_all() — SQLite.
2. v2 (future): Alembic revisions for PostgreSQL, with `alembic init` and
   `alembic revision --autogenerate`.
3. Keep `app/database/migrations/` for versioned SQL/Alembic scripts.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION"]
