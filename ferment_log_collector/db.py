from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Device, DeviceStatus, utc_now_iso


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 300,
    enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_status (
    device_id INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    last_fetch_at TEXT,
    last_success_at TEXT,
    last_new_archive_at TEXT,
    last_http_status INTEGER,
    last_error TEXT,
    rows_collected INTEGER NOT NULL DEFAULT 0,
    last_archive_sha256 TEXT,
    latest_archive_path TEXT,
    live_snapshot_at TEXT,
    live_snapshot_error TEXT
);

CREATE TABLE IF NOT EXISTS archives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    appended_row_count INTEGER NOT NULL,
    UNIQUE(device_id, sha256)
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def list_devices_with_status(self) -> list[tuple[Device, DeviceStatus]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.*, s.last_fetch_at, s.last_success_at, s.last_new_archive_at, s.last_http_status,
                       s.last_error, s.rows_collected, s.last_archive_sha256, s.latest_archive_path,
                       s.live_snapshot_at, s.live_snapshot_error
                FROM devices d
                JOIN device_status s ON s.device_id = d.id
                ORDER BY d.name COLLATE NOCASE
                """
            ).fetchall()
        return [(device_from_row(row), status_from_row(row)) for row in rows]

    def get_device(self, device_id: int) -> Device | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return device_from_row(row) if row else None

    def enabled_devices(self) -> list[Device]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM devices WHERE enabled = 1 ORDER BY id").fetchall()
        return [device_from_row(row) for row in rows]

    def upsert_device(
        self,
        *,
        name: str,
        slug: str,
        base_url: str,
        polling_interval_seconds: int,
        enabled: bool,
        device_id: int | None = None,
    ) -> int:
        now = utc_now_iso()
        with self.connect() as conn:
            if device_id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO devices (name, slug, base_url, polling_interval_seconds, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, slug, base_url, polling_interval_seconds, int(enabled), now, now),
                )
                new_id = int(cursor.lastrowid)
                conn.execute("INSERT INTO device_status (device_id) VALUES (?)", (new_id,))
                return new_id

            conn.execute(
                """
                UPDATE devices
                SET name = ?, slug = ?, base_url = ?, polling_interval_seconds = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, slug, base_url, polling_interval_seconds, int(enabled), now, device_id),
            )
            return device_id

    def delete_device(self, device_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    def set_fetch_started(self, device_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE device_status SET last_fetch_at = ?, last_error = NULL, last_http_status = NULL WHERE device_id = ?",
                (utc_now_iso(), device_id),
            )

    def set_fetch_result(self, device_id: int, *, http_status: int | None, error: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE device_status
                SET last_fetch_at = ?, last_http_status = ?, last_error = ?
                WHERE device_id = ?
                """,
                (utc_now_iso(), http_status, error, device_id),
            )

    def set_live_snapshot_result(self, device_id: int, error: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE device_status
                SET live_snapshot_at = ?, live_snapshot_error = ?
                WHERE device_id = ?
                """,
                (utc_now_iso(), error, device_id),
            )

    def archive_exists(self, device_id: int, sha256: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM archives WHERE device_id = ? AND sha256 = ?",
                (device_id, sha256),
            ).fetchone()
        return row is not None

    def record_archive(
        self,
        *,
        device_id: int,
        sha256: str,
        raw_path: str,
        row_count: int,
        appended_row_count: int,
    ) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO archives (device_id, sha256, fetched_at, raw_path, row_count, appended_row_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, sha256, now, raw_path, row_count, appended_row_count),
            )
            conn.execute(
                """
                UPDATE device_status
                SET last_fetch_at = ?,
                    last_success_at = ?,
                    last_new_archive_at = ?,
                    last_error = NULL,
                    rows_collected = rows_collected + ?,
                    last_archive_sha256 = ?,
                    latest_archive_path = ?,
                    last_http_status = 200
                WHERE device_id = ?
                """,
                (now, now, now, appended_row_count, sha256, raw_path, device_id),
            )

    def record_duplicate_success(self, device_id: int, sha256: str) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE device_status
                SET last_fetch_at = ?, last_success_at = ?, last_error = NULL, last_archive_sha256 = ?, last_http_status = 200
                WHERE device_id = ?
                """,
                (now, now, sha256, device_id),
            )


def device_from_row(row: sqlite3.Row) -> Device:
    return Device(
        id=int(row["id"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        base_url=str(row["base_url"]),
        polling_interval_seconds=int(row["polling_interval_seconds"]),
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def status_from_row(row: sqlite3.Row) -> DeviceStatus:
    return DeviceStatus(
        device_id=int(row["id"]),
        last_fetch_at=row["last_fetch_at"],
        last_success_at=row["last_success_at"],
        last_new_archive_at=row["last_new_archive_at"],
        last_http_status=row["last_http_status"],
        last_error=row["last_error"],
        rows_collected=int(row["rows_collected"]),
        last_archive_sha256=row["last_archive_sha256"],
        latest_archive_path=row["latest_archive_path"],
        live_snapshot_at=row["live_snapshot_at"],
        live_snapshot_error=row["live_snapshot_error"],
    )
