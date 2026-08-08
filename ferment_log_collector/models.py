from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Device:
    id: int
    name: str
    slug: str
    base_url: str
    polling_interval_seconds: int
    enabled: bool
    created_at: str
    updated_at: str


@dataclass(slots=True)
class DeviceStatus:
    device_id: int
    last_fetch_at: str | None
    last_success_at: str | None
    last_new_archive_at: str | None
    last_http_status: int | None
    last_error: str | None
    rows_collected: int
    last_archive_sha256: str | None
    latest_archive_path: str | None
    live_snapshot_at: str | None
    live_snapshot_error: str | None


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
