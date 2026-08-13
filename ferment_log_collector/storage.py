from __future__ import annotations

import csv
import hashlib
import io
from collections import deque
from datetime import datetime
from pathlib import Path

from .models import Device


class CollectorStorage:
    def __init__(self, root: Path) -> None:
        self.data_root = root
        self.logs_root = root.parent / "logs"
        self.collector_log_root = self.logs_root / "collector"
        self.device_log_root = self.logs_root / "devices"
        for path in (self.data_root, self.collector_log_root, self.device_log_root):
            path.mkdir(parents=True, exist_ok=True)

    def archive_url(self, device: Device) -> str:
        return join_url(device.base_url, "/glycol_log.archived.csv")

    def live_url(self, device: Device) -> str:
        return join_url(device.base_url, "/glycol_log.csv")

    def sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def save_raw_archive(self, device: Device, digest: str, content: bytes) -> Path:
        archives_dir = self.archive_dir(device)
        archives_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
        timestamp = timestamp.replace(":", "-")
        path = archives_dir / f"{timestamp}_{digest[:8]}.csv"
        path.write_bytes(content)
        return path

    def save_live_snapshot(self, device: Device, content: bytes) -> Path:
        device_dir = self.device_dir(device)
        device_dir.mkdir(parents=True, exist_ok=True)
        path = device_dir / "glycol_log_live.csv"
        path.write_bytes(content)
        return path

    def combined_csv_path(self, device: Device) -> Path:
        device_dir = self.device_dir(device)
        device_dir.mkdir(parents=True, exist_ok=True)
        return device_dir / "glycol_log_combined.csv"

    def latest_archive_path(self, device: Device) -> Path | None:
        archives = sorted(self.archive_dir(device).glob("*.csv"), reverse=True)
        return archives[0] if archives else None

    def live_snapshot_path(self, device: Device) -> Path:
        return self.device_dir(device) / "glycol_log_live.csv"

    def archive_dir(self, device: Device) -> Path:
        return self.device_dir(device) / "archives"

    def device_dir(self, device: Device) -> Path:
        return self.device_log_root / device.slug

    def append_archive_to_combined(self, device: Device, content: bytes) -> tuple[int, int]:
        rows = self._csv_rows(content)
        if not rows:
            return 0, 0

        header = rows[0]
        data_rows = rows[1:]
        combined_path = self.combined_csv_path(device)
        combined_exists = combined_path.exists() and combined_path.stat().st_size > 0

        with combined_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if not combined_exists:
                writer.writerow(header)
            writer.writerows(data_rows)

        return len(data_rows), len(data_rows)

    def count_data_rows(self, content: bytes) -> int:
        rows = self._csv_rows(content)
        return max(len(rows) - 1, 0)

    def csv_preview(self, path: Path, tail: int) -> dict[str, object]:
        rows = self._csv_rows(path.read_bytes())
        if not rows:
            return {"columns": [], "rows": [], "total_rows": 0}

        columns = rows[0]
        data_rows = rows[1:]
        return {
            "columns": columns,
            "rows": data_rows[-tail:],
            "total_rows": len(data_rows),
        }

    def text_tail(self, path: Path, tail: int) -> dict[str, object]:
        lines: deque[str] = deque(maxlen=tail)
        line_count = 0
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line_count += 1
                lines.append(line.rstrip("\n"))
        return {"lines": list(lines), "total_lines": line_count}

    def _csv_rows(self, content: bytes) -> list[list[str]]:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        return [row for row in reader if row and any(cell.strip() for cell in row)]

    def audit(self, level: str, device: Device, message: str, **fields: object) -> None:
        self.collector_log_root.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone().replace(microsecond=0)
        path = self.collector_log_root / f"collector-{now.strftime('%Y-%m')}.log"
        parts = [now.isoformat(), level.upper(), device.name, message]
        for key, value in fields.items():
            if value is not None:
                parts.append(f"{key}={value}")
        line = " ".join(parts) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def current_audit_path(self) -> Path:
        now = datetime.now().astimezone()
        return self.collector_log_root / f"collector-{now.strftime('%Y-%m')}.log"


def join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")
