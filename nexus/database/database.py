"""Engine/session factory with simple schema versioning.

SQLite is the default. Because all access goes through SQLAlchemy, switching to PostgreSQL only
requires NEXUS_DATABASE_URL (see docs/feasibility.md for the pgvector migration path).
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from nexus.database.models import SCHEMA_VERSION, Base, SchemaVersion
from nexus.utils.config import get_settings

_engines: dict[str, object] = {}


def get_engine(url: str | None = None):
    url = url or get_settings().database_url
    if url not in _engines:
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        engine = create_engine(url, future=True, **kwargs)
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            current = s.scalar(select(SchemaVersion.version).order_by(SchemaVersion.version.desc()))
            if current is None:
                s.add(SchemaVersion(version=SCHEMA_VERSION))
                s.commit()
            elif current > SCHEMA_VERSION:
                raise RuntimeError(f"Database schema v{current} is newer than this code (v{SCHEMA_VERSION}).")
            elif current < SCHEMA_VERSION:
                _migrate(s, current)
        _engines[url] = engine
    return _engines[url]


# Column additions per schema version. New tables are created by create_all(); only columns added to
# existing tables need explicit statements. Derived rows are rebuilt by recompute() afterwards.
MIGRATIONS = {
    2: ["ALTER TABLE company ADD COLUMN need_priorities JSON DEFAULT '[]'",
        "ALTER TABLE opportunity ADD COLUMN base_relevance FLOAT DEFAULT 0",
        "ALTER TABLE opportunity ADD COLUMN adjustments JSON DEFAULT '[]'"],
    3: ["ALTER TABLE company ADD COLUMN field_sources JSON DEFAULT '{}'",
        "ALTER TABLE company ADD COLUMN missing_fields JSON DEFAULT '[]'",
        "ALTER TABLE company ADD COLUMN last_verified_at DATETIME",
        "ALTER TABLE company ADD COLUMN profile_fetch_status VARCHAR(200)",
        "ALTER TABLE company ADD COLUMN directory_snapshot_id VARCHAR(60)",
        "ALTER TABLE company ADD COLUMN listing_status VARCHAR(40)",
        "ALTER TABLE company ADD COLUMN membership_classification VARCHAR(60) "
        "DEFAULT 'member_or_partner_not_individually_disclosed'",
        "ALTER TABLE company ADD COLUMN aliases JSON DEFAULT '[]'"],
    4: ["ALTER TABLE company ADD COLUMN share_refinements BOOLEAN DEFAULT 0",
        "ALTER TABLE opportunity ADD COLUMN audience VARCHAR(10) DEFAULT 'public'",
        "ALTER TABLE collaboration_hypothesis ADD COLUMN visibility VARCHAR(30) DEFAULT 'public'",
        "ALTER TABLE recommendation ADD COLUMN audience VARCHAR(10) DEFAULT 'public'"],
}


def _migrate(s: Session, current: int) -> None:
    from sqlalchemy import text

    for version in range(current + 1, SCHEMA_VERSION + 1):
        for stmt in MIGRATIONS.get(version, []):
            try:
                s.execute(text(stmt))
            except Exception:  # column already exists (fresh table created by create_all)
                s.rollback()
        s.add(SchemaVersion(version=version))
        s.commit()


def get_sessionmaker(url: str | None = None) -> sessionmaker:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False, future=True)


@contextmanager
def session_scope(url: str | None = None):
    session = get_sessionmaker(url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
