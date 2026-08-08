import httpx

from ferment_log_collector.health import check_device_health
from ferment_log_collector.models import Device
from ferment_log_collector.storage import CollectorStorage


async def test_device_health_reports_online_with_missing_archive(tmp_path):
    storage = CollectorStorage(tmp_path / "data")
    device = Device(
        id=1,
        name="TresFermTrack-1",
        slug="tresfermtrack-1",
        base_url="http://example.local",
        polling_interval_seconds=300,
        enabled=True,
        created_at="now",
        updated_at="now",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/glycol_log.csv":
            return httpx.Response(200, content=b"timestamp,millis\n")
        if request.url.path == "/glycol_log.archived.csv":
            return httpx.Response(404)
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        device_id, health = await check_device_health(device, storage, client)

    assert device_id == device.id
    assert health.online is True
    assert health.live_file.present is True
    assert health.archive_file.status_code == 404
    assert health.archive_file.present is False
