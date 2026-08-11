from ferment_log_collector.db import Database


def test_init_does_not_seed_devices(tmp_path):
    db = Database(tmp_path / "collector.sqlite3")

    db.init()

    assert db.list_devices_with_status() == []
