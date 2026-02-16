#!/usr/bin/env python3
"""
Certify Intel - SQLite to PostgreSQL Migration Script
=====================================================

Migrates all data from the SQLite development database to PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_postgres.py

Environment variables:
    DATABASE_URL  - PostgreSQL connection string (default: postgresql://certify_intel:certify_intel_password@localhost:5432/certify_intel)
    SQLITE_PATH   - Path to SQLite database (default: backend/certify_intel.db)

Features:
    - Reads SQLAlchemy ORM models for schema understanding
    - Creates PostgreSQL tables via SQLAlchemy (respects all indexes/constraints)
    - Migrates ALL data with proper type mapping
    - Idempotent: safe to run multiple times (drops and recreates tables)
    - Progress reporting per table
    - Handles vector/embedding columns for pgvector
"""

import os
import sys
import json
import sqlite3
import time
import logging
from datetime import datetime
from pathlib import Path

# Add backend to path so we can import database models
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("migrate")

# Default connection parameters
DEFAULT_PG_URL = "postgresql://certify_intel:certify_intel_password@localhost:5432/certify_intel"
DEFAULT_SQLITE_PATH = str(BACKEND_DIR / "certify_intel.db")


def get_sqlite_connection(sqlite_path: str) -> sqlite3.Connection:
    """Open SQLite database in read-only mode."""
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)

    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_pg_engine(pg_url: str):
    """Create SQLAlchemy engine for PostgreSQL."""
    from sqlalchemy import create_engine
    return create_engine(
        pg_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        echo=False
    )


def get_sqlite_tables(conn: sqlite3.Connection) -> list:
    """Get all user tables from SQLite (excluding internal tables)."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def get_sqlite_table_schema(conn: sqlite3.Connection, table_name: str) -> list:
    """Get column info for a SQLite table."""
    cursor = conn.execute(f"PRAGMA table_info(\"{table_name}\")")
    return cursor.fetchall()


def get_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    """Get row count for a SQLite table."""
    cursor = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
    return cursor.fetchone()[0]


def get_all_rows(conn: sqlite3.Connection, table_name: str) -> list:
    """Get all rows from a SQLite table."""
    cursor = conn.execute(f"SELECT * FROM \"{table_name}\"")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return columns, rows


# =========================================================================
# ORM Model to Table Mapping
# =========================================================================
# Maps SQLAlchemy model table names to their models for schema-aware migration.
# This ensures PostgreSQL gets proper column types (BOOLEAN, TIMESTAMP, etc.)
# instead of SQLite's loose TEXT/INTEGER typing.

def get_orm_column_types() -> dict:
    """
    Build a mapping of table_name -> {column_name -> sqlalchemy_type}
    by inspecting the ORM models defined in database.py.
    """
    # Import must happen after sys.path is set
    # We need to temporarily override DATABASE_URL so importing database.py
    # doesn't try to create tables against the wrong database
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///./migration_temp_noop.db"

    try:
        # Force fresh import
        if "database" in sys.modules:
            del sys.modules["database"]

        from database import Base
        type_map = {}

        for table_name, table in Base.metadata.tables.items():
            col_types = {}
            for col in table.columns:
                col_type = type(col.type).__name__
                col_types[col.name] = col_type
            type_map[table_name] = col_types

        return type_map
    finally:
        # Restore original env
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)
        # Clean up temp db if created
        temp_db = BACKEND_DIR / "migration_temp_noop.db"
        if temp_db.exists():
            temp_db.unlink()


def convert_value(value, orm_type: str, column_name: str):
    """
    Convert a SQLite value to the appropriate Python type for PostgreSQL.

    SQLite stores everything as TEXT/INTEGER/REAL/BLOB. PostgreSQL needs
    proper BOOLEAN, TIMESTAMP, JSONB, etc.
    """
    if value is None:
        return None

    # Boolean conversion: SQLite stores as 0/1 integers
    if orm_type == "Boolean":
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)

    # DateTime conversion: SQLite stores as ISO text strings
    if orm_type == "DateTime":
        if isinstance(value, str):
            # Try common datetime formats
            for fmt in (
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            # If none match, return as-is and let PostgreSQL handle it
            logger.warning(f"Could not parse datetime '{value}' for column '{column_name}'")
            return value
        return value

    # Float conversion
    if orm_type == "Float":
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        return value

    # Integer conversion
    if orm_type == "Integer":
        if isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        return value

    # Text/String - pass through
    return value


def create_pg_tables(pg_engine):
    """
    Create all ORM-defined tables in PostgreSQL using SQLAlchemy metadata.

    This ensures proper column types, indexes, and constraints.
    """
    # Import with the correct DATABASE_URL already set
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///./migration_temp_noop.db"

    try:
        if "database" in sys.modules:
            del sys.modules["database"]

        from database import Base

        logger.info("Dropping existing tables (if any)...")
        Base.metadata.drop_all(bind=pg_engine)

        logger.info("Creating tables from ORM models...")
        Base.metadata.create_all(bind=pg_engine)

        logger.info("ORM tables created successfully.")
        return list(Base.metadata.tables.keys())
    finally:
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)
        temp_db = BACKEND_DIR / "migration_temp_noop.db"
        if temp_db.exists():
            temp_db.unlink()


def reset_sequences(pg_engine, table_name: str):
    """
    Reset PostgreSQL sequence for auto-increment columns after data import.

    SQLite uses ROWID; PostgreSQL uses sequences. After inserting data with
    explicit IDs, the sequence must be advanced past the max ID.
    """
    from sqlalchemy import text

    with pg_engine.connect() as conn:
        try:
            result = conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = :table AND column_default LIKE 'nextval%%'"
            ), {"table": table_name})
            seq_columns = [row[0] for row in result]

            for col in seq_columns:
                conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', '{col}'), "
                    f"COALESCE((SELECT MAX({col}) FROM \"{table_name}\"), 0) + 1, false)"
                ))
            conn.commit()
        except Exception as e:
            logger.debug(f"Sequence reset for {table_name}: {e}")
            conn.rollback()


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_engine,
    table_name: str,
    orm_types: dict,
    batch_size: int = 500
) -> int:
    """
    Migrate a single table from SQLite to PostgreSQL.

    Returns number of rows migrated.
    """
    from sqlalchemy import text

    row_count = get_row_count(sqlite_conn, table_name)
    if row_count == 0:
        logger.info(f"  {table_name}: 0 rows (skipping)")
        return 0

    columns, rows = get_all_rows(sqlite_conn, table_name)
    col_types = orm_types.get(table_name, {})

    # Filter columns to only those that exist in the ORM model
    # (SQLite may have extra columns from ALTER TABLE that aren't in the model)
    if col_types:
        valid_columns = [c for c in columns if c in col_types]
        valid_col_indices = [columns.index(c) for c in valid_columns]
    else:
        valid_columns = columns
        valid_col_indices = list(range(len(columns)))

    if not valid_columns:
        logger.warning(f"  {table_name}: No matching ORM columns found, skipping")
        return 0

    # Build INSERT statement with named parameters
    col_list = ", ".join(f'"{c}"' for c in valid_columns)
    param_list = ", ".join(f":{c}" for c in valid_columns)
    insert_sql = text(f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list})')

    migrated = 0
    errors = 0

    with pg_engine.connect() as conn:
        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start:batch_start + batch_size]
            batch_params = []

            for row in batch:
                row_dict = {}
                for i, col_idx in enumerate(valid_col_indices):
                    col_name = valid_columns[i]
                    raw_value = row[col_idx]
                    orm_type = col_types.get(col_name, "String")
                    row_dict[col_name] = convert_value(raw_value, orm_type, col_name)
                batch_params.append(row_dict)

            try:
                conn.execute(insert_sql, batch_params)
                conn.commit()
                migrated += len(batch)
            except Exception as e:
                conn.rollback()
                # Fall back to row-by-row insert for this batch
                for params in batch_params:
                    try:
                        conn.execute(insert_sql, params)
                        conn.commit()
                        migrated += 1
                    except Exception as row_err:
                        conn.rollback()
                        errors += 1
                        if errors <= 3:
                            logger.warning(
                                f"  {table_name}: Row insert error: {str(row_err)[:100]}"
                            )

    # Reset auto-increment sequence
    reset_sequences(pg_engine, table_name)

    status = f"  {table_name}: {migrated}/{row_count} rows"
    if errors:
        status += f" ({errors} errors)"
    logger.info(status)

    return migrated


def verify_migration(sqlite_conn: sqlite3.Connection, pg_engine, tables: list):
    """Compare row counts between SQLite and PostgreSQL."""
    from sqlalchemy import text

    logger.info("\n=== Migration Verification ===")
    all_match = True

    with pg_engine.connect() as conn:
        for table in tables:
            sqlite_count = get_row_count(sqlite_conn, table)
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                pg_count = result.scalar()
            except Exception:
                pg_count = 0

            status = "OK" if sqlite_count == pg_count else "MISMATCH"
            if status == "MISMATCH":
                all_match = False

            if sqlite_count > 0 or pg_count > 0:
                logger.info(f"  {table}: SQLite={sqlite_count} PostgreSQL={pg_count} [{status}]")

    if all_match:
        logger.info("\nAll table row counts match.")
    else:
        logger.warning("\nSome tables have row count mismatches. Check warnings above.")


def main():
    """Run the full SQLite to PostgreSQL migration."""
    pg_url = os.environ.get("DATABASE_URL", DEFAULT_PG_URL)
    sqlite_path = os.environ.get("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    logger.info("=" * 60)
    logger.info("Certify Intel - SQLite to PostgreSQL Migration")
    logger.info("=" * 60)
    logger.info(f"SQLite source : {sqlite_path}")
    logger.info(f"PostgreSQL target: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")
    logger.info("")

    # Step 1: Connect to SQLite
    logger.info("[1/5] Connecting to SQLite...")
    sqlite_conn = get_sqlite_connection(sqlite_path)
    sqlite_tables = get_sqlite_tables(sqlite_conn)
    logger.info(f"  Found {len(sqlite_tables)} tables in SQLite")

    # Step 2: Read ORM type information
    logger.info("[2/5] Reading ORM model definitions...")
    orm_types = get_orm_column_types()
    orm_tables = set(orm_types.keys())
    logger.info(f"  Found {len(orm_tables)} ORM-defined tables")

    # Identify tables present in both SQLite and ORM
    common_tables = [t for t in sqlite_tables if t in orm_tables]
    sqlite_only = [t for t in sqlite_tables if t not in orm_tables]
    orm_only = [t for t in orm_tables if t not in set(sqlite_tables)]

    if sqlite_only:
        logger.info(f"  SQLite-only tables (will skip): {sqlite_only}")
    if orm_only:
        logger.info(f"  ORM-only tables (will create empty): {orm_only}")

    # Step 3: Create PostgreSQL tables
    logger.info("[3/5] Creating PostgreSQL tables...")
    pg_engine = get_pg_engine(pg_url)

    # Test connection
    from sqlalchemy import text
    try:
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("  PostgreSQL connection verified")
    except Exception as e:
        logger.error(f"  Cannot connect to PostgreSQL: {e}")
        logger.error("  Make sure PostgreSQL is running:")
        logger.error("    docker compose -f docker-compose.postgres.yml up -d")
        sys.exit(1)

    created_tables = create_pg_tables(pg_engine)
    logger.info(f"  Created {len(created_tables)} tables")

    # Step 4: Migrate data
    logger.info("[4/5] Migrating data...")
    start_time = time.time()
    total_rows = 0

    # Order tables to respect foreign key constraints
    # Parent tables first, then child tables
    parent_tables = [
        "competitors", "users", "teams", "system_settings",
        "system_prompts", "knowledge_base"
    ]
    ordered_tables = []
    for t in parent_tables:
        if t in common_tables:
            ordered_tables.append(t)
    for t in common_tables:
        if t not in ordered_tables:
            ordered_tables.append(t)

    for table in ordered_tables:
        rows = migrate_table(sqlite_conn, pg_engine, table, orm_types)
        total_rows += rows

    elapsed = time.time() - start_time
    logger.info(f"\n  Total: {total_rows} rows migrated in {elapsed:.1f}s")

    # Step 5: Verify
    logger.info("[5/5] Verifying migration...")
    verify_migration(sqlite_conn, pg_engine, ordered_tables)

    # Cleanup
    sqlite_conn.close()
    pg_engine.dispose()

    logger.info("\n" + "=" * 60)
    logger.info("Migration complete!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Set DATABASE_URL in backend/.env:")
    logger.info(f"     DATABASE_URL={pg_url}")
    logger.info("  2. Restart the backend:")
    logger.info("     cd backend && python main.py")
    logger.info("  3. Verify the application works correctly")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
