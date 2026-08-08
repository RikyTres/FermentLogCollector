from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

from .db import Database
from .models import Device
from .storage import CollectorStorage


@dataclass
class PollRuntime:
    next_due: float = 0
    running: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Collector:
    def __init__(self, db: Database, storage: CollectorStorage) -> None:
        self.db = db
        self.storage = storage
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._runtime: dict[int, PollRuntime] = {}

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="ferment-log-poller")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            now = asyncio.get_running_loop().time()
            for device in self.db.enabled_devices():
                runtime = self._runtime.setdefault(device.id, PollRuntime())
                if now >= runtime.next_due and not runtime.running:
                    runtime.next_due = now + max(device.polling_interval_seconds, 10)
                    asyncio.create_task(self.poll_device(device))
            await asyncio.sleep(2)

    async def poll_device(self, device: Device) -> None:
        runtime = self._runtime.setdefault(device.id, PollRuntime())
        async with runtime.lock:
            runtime.running = True
            try:
                await self._poll_device(device)
            finally:
                runtime.running = False

    async def _poll_device(self, device: Device) -> None:
        url = self.storage.archive_url(device)
        started = time.perf_counter()
        self.db.set_fetch_started(device.id)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            message = f"HTTP error while fetching archive: {exc}"
            self.db.set_fetch_result(device.id, http_status=None, error=message)
            self.storage.audit("ERROR", device, "fetch failed", error=str(exc), duration_ms=duration_ms)
            return

        duration_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code == 404:
            self.db.set_fetch_result(device.id, http_status=404, error=None)
            self.storage.audit(
                "WARN",
                device,
                "archived log not found",
                status=404,
                duration_ms=duration_ms,
            )
            return

        if response.status_code >= 400:
            message = f"archive fetch failed with HTTP {response.status_code}"
            self.db.set_fetch_result(device.id, http_status=response.status_code, error=message)
            self.storage.audit(
                "ERROR",
                device,
                "archive fetch failed",
                status=response.status_code,
                duration_ms=duration_ms,
            )
            return

        content = response.content
        digest = self.storage.sha256(content)
        if self.db.archive_exists(device.id, digest):
            self.db.record_duplicate_success(device.id, digest)
            row_count = self.storage.count_data_rows(content)
            self.storage.audit(
                "INFO",
                device,
                "archived log unchanged",
                hash=digest,
                bytes=len(content),
                rows=row_count,
                duration_ms=duration_ms,
            )
            return

        raw_path = self.storage.save_raw_archive(device, digest, content)
        row_count, appended_count = self.storage.append_archive_to_combined(device, content)
        self.db.record_archive(
            device_id=device.id,
            sha256=digest,
            raw_path=str(raw_path),
            row_count=row_count,
            appended_row_count=appended_count,
        )
        self.storage.audit(
            "INFO",
            device,
            "new archived log appended",
            hash=digest,
            rows_appended=appended_count,
            rows=row_count,
            bytes=len(content),
            duration_ms=duration_ms,
            archive_path=raw_path,
        )

    async def fetch_live_snapshot(self, device: Device) -> tuple[bool, str]:
        url = self.storage.live_url(device)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
            duration_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                message = f"live snapshot failed with HTTP {response.status_code}"
                self.db.set_live_snapshot_result(device.id, message)
                self.storage.audit(
                    "ERROR",
                    device,
                    "live snapshot failed",
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
                return False, message
            path = self.storage.save_live_snapshot(device, response.content)
            self.db.set_live_snapshot_result(device.id, None)
            self.storage.audit(
                "INFO",
                device,
                "live snapshot saved",
                status=response.status_code,
                bytes=len(response.content),
                duration_ms=duration_ms,
                snapshot_path=path,
            )
            return True, str(path)
        except httpx.HTTPError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            message = f"HTTP error while fetching live snapshot: {exc}"
            self.db.set_live_snapshot_result(device.id, message)
            self.storage.audit("ERROR", device, "live snapshot failed", error=str(exc), duration_ms=duration_ms)
            return False, message
