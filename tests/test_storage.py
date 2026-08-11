from ferment_log_collector.models import Device
from ferment_log_collector.storage import CollectorStorage


def test_append_archive_writes_header_once(tmp_path):
    storage = CollectorStorage(tmp_path / "data")
    device = Device(
        id=1,
        name="Fermenter-1",
        slug="fermenter-1",
        base_url="http://example.local",
        polling_interval_seconds=300,
        enabled=True,
        created_at="now",
        updated_at="now",
    )

    csv_a = b"time,event,value\n2026-01-01T00:00:00Z,pump_on,1\n"
    csv_b = b"time,event,value\n2026-01-01T00:01:00Z,pump_off,0\n"

    assert storage.append_archive_to_combined(device, csv_a) == (1, 1)
    assert storage.append_archive_to_combined(device, csv_b) == (1, 1)

    combined = storage.combined_csv_path(device).read_text(encoding="utf-8")
    assert combined.count("time,event,value") == 1
    assert "pump_on" in combined
    assert "pump_off" in combined


def test_storage_uses_documented_device_layout(tmp_path):
    storage = CollectorStorage(tmp_path / "data")
    device = Device(
        id=1,
        name="Fermenter-1",
        slug="fermenter-1",
        base_url="http://example.local",
        polling_interval_seconds=300,
        enabled=True,
        created_at="now",
        updated_at="now",
    )

    device_root = tmp_path / "logs" / "devices" / "fermenter-1"
    assert storage.combined_csv_path(device) == device_root / "glycol_log_combined.csv"
    assert storage.live_snapshot_path(device) == device_root / "glycol_log_live.csv"
    assert storage.archive_dir(device) == device_root / "archives"


def test_archive_urls_are_normalized(tmp_path):
    storage = CollectorStorage(tmp_path / "data")
    device = Device(
        id=1,
        name="Device",
        slug="device",
        base_url="http://example.local/",
        polling_interval_seconds=300,
        enabled=True,
        created_at="now",
        updated_at="now",
    )

    assert storage.archive_url(device) == "http://example.local/glycol_log.archived.csv"
    assert storage.live_url(device) == "http://example.local/glycol_log.csv"
