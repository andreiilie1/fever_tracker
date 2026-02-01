from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(
        DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    with conn:  # ensure pragma is applied
        conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS medication_names (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS measurements (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at   TEXT NOT NULL,            -- ISO-8601 datetime string
                temperature_c REAL NOT NULL,
                notes         TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_recorded_at
                ON measurements(recorded_at);

            CREATE TABLE IF NOT EXISTS medications (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                given_at  TEXT NOT NULL,               -- ISO-8601 datetime string
                med_name  TEXT NOT NULL,
                dose_desc TEXT,                        -- e.g., "5 ml" or "120 mg"
                notes     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_medications_given_at
                ON medications(given_at);

            -- Seed medication_names from existing medications if not present
            INSERT OR IGNORE INTO medication_names(name)
            SELECT DISTINCT med_name FROM medications WHERE med_name IS NOT NULL AND TRIM(med_name) <> '';
            """)


def fetch_medication_names() -> pd.DataFrame:
    with _get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT id, name FROM medication_names ORDER BY LOWER(name) ASC", conn
        )
    return df


def add_medication_name(name: str) -> int:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Medication name cannot be empty.")
    with _get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO medication_names(name) VALUES (?)", (cleaned,)
        )
        row = conn.execute(
            "SELECT id FROM medication_names WHERE name = ?", (cleaned,)
        ).fetchone()
        return int(row[0])


def update_medication_name(row_id: int, name: str) -> None:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Medication name cannot be empty.")
    with _get_connection() as conn:
        conn.execute(
            "UPDATE medication_names SET name = ? WHERE id = ?", (cleaned, int(row_id))
        )


def delete_medication_name(row_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM medication_names WHERE id = ?", (int(row_id),))


# Write operations
def add_measurement(
    recorded_at_iso: str, temperature_c: float, notes: Optional[str] = None
) -> int:
    with _get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO measurements (recorded_at, temperature_c, notes) VALUES (?, ?, ?)",
            (recorded_at_iso, float(temperature_c), notes),
        )
        return int(cur.lastrowid)


def add_medication(
    given_at_iso: str,
    med_name: str,
    dose_desc: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    with _get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO medications (given_at, med_name, dose_desc, notes) VALUES (?, ?, ?, ?)",
            (given_at_iso, med_name, dose_desc, notes),
        )
        return int(cur.lastrowid)


def update_measurement(
    row_id: int, recorded_at_iso: str, temperature_c: float, notes: Optional[str]
) -> None:
    with _get_connection() as conn:
        conn.execute(
            "UPDATE measurements SET recorded_at = ?, temperature_c = ?, notes = ? WHERE id = ?",
            (recorded_at_iso, float(temperature_c), notes, int(row_id)),
        )


def update_medication(
    row_id: int,
    given_at_iso: str,
    med_name: str,
    dose_desc: Optional[str],
    notes: Optional[str],
) -> None:
    with _get_connection() as conn:
        conn.execute(
            "UPDATE medications SET given_at = ?, med_name = ?, dose_desc = ?, notes = ? WHERE id = ?",
            (given_at_iso, med_name, dose_desc, notes, int(row_id)),
        )


# Read operations
def fetch_measurements(limit: Optional[int] = None) -> pd.DataFrame:
    query = "SELECT id, recorded_at, temperature_c, notes FROM measurements ORDER BY recorded_at ASC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    with _get_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def fetch_medications(limit: Optional[int] = None) -> pd.DataFrame:
    query = "SELECT id, given_at, med_name, dose_desc, notes FROM medications ORDER BY given_at ASC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    with _get_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def export_table_as_csv(table_name: str) -> str:
    if table_name not in {"measurements", "medications"}:
        raise ValueError("Unsupported table for export.")
    with _get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY 1 ASC", conn)
    return df.to_csv(index=False)


def delete_entry(table_name: str, row_id: int) -> None:
    if table_name not in {"measurements", "medications"}:
        raise ValueError("Unsupported table.")
    with _get_connection() as conn:
        conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (int(row_id),))
