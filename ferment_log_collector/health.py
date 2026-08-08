from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from .models import Device
from .storage import CollectorStorage


@dataclass(slots=True)
class EndpointProbe:
    status_code: int | None
    error: str | None = None

    @property
    def responded(self) -> bool:
        return self.status_code is not None

    @property
    def present(self) -> bool:
        return self.status_code in {200, 206}


@dataclass(slots=True)
class DeviceHealth:
    online: bool
    live_file: EndpointProbe
    archive_file: EndpointProbe


async def check_devices_health(
    devices: list[Device],
    storage: CollectorStorage,
    *,
    timeout_seconds: float = 2.0,
) -> dict[int, DeviceHealth]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        checks = [check_device_health(device, storage, client) for device in devices]
        results = await asyncio.gather(*checks)
    return dict(results)


async def check_device_health(
    device: Device,
    storage: CollectorStorage,
    client: httpx.AsyncClient,
) -> tuple[int, DeviceHealth]:
    live_probe, archive_probe = await asyncio.gather(
        probe_url(client, storage.live_url(device)),
        probe_url(client, storage.archive_url(device)),
    )
    health = DeviceHealth(
        online=live_probe.responded or archive_probe.responded,
        live_file=live_probe,
        archive_file=archive_probe,
    )
    return device.id, health


async def probe_url(client: httpx.AsyncClient, url: str) -> EndpointProbe:
    try:
        response = await client.get(url, headers={"Range": "bytes=0-0"})
    except httpx.HTTPError as exc:
        return EndpointProbe(status_code=None, error=exc.__class__.__name__)
    return EndpointProbe(status_code=response.status_code)
