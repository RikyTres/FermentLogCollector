# FermentLogCollector

Small local FastAPI service that collects BrewPi-ESP glycol log archive segments.

The collector polls each enabled device at `/glycol_log.archived.csv`, hashes the
CSV with SHA-256, deduplicates already-seen archives, stores the raw archive, and
appends only new data rows to a long per-device combined CSV.

## Installation

This repository is private. For an unattended collector host, prefer SSH access
with a dedicated deploy key or machine user.

Install a stable release tag instead of tracking the latest `master` branch:

```sh
sudo mkdir -p /opt/FermentLogCollector
sudo chown "$USER":"$(id -gn)" /opt/FermentLogCollector
git clone git@github.com:RikyTres/FermentLogCollector.git /opt/FermentLogCollector
cd /opt/FermentLogCollector
git fetch --tags
git checkout v0.1.0
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
FERMENT_COLLECTOR_DATA_DIR=/var/lib/fermentlogcollector .venv/bin/python -m uvicorn ferment_log_collector.main:app --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000.

If a release tag is not available yet, pin an exact commit instead:

```sh
git checkout <commit-sha>
```

The app creates its SQLite database under `data/` and collected logs under
`logs/` by default. For a persistent install, set `FERMENT_COLLECTOR_DATA_DIR`
to a stable writable directory such as `/var/lib/fermentlogcollector`.

### Updating

Updates should be intentional:

```sh
cd /opt/FermentLogCollector
git fetch --tags
git checkout v0.1.1
. .venv/bin/activate
python -m pip install .
sudo systemctl restart fermentlogcollector
```

### Systemd Service

On a Linux host, create `/etc/systemd/system/fermentlogcollector.service`:

```ini
[Unit]
Description=FermentLogCollector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/FermentLogCollector
Environment=FERMENT_COLLECTOR_DATA_DIR=/var/lib/fermentlogcollector
ExecStart=/opt/FermentLogCollector/.venv/bin/python -m uvicorn ferment_log_collector.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable it:

```sh
sudo mkdir -p /var/lib/fermentlogcollector
sudo systemctl daemon-reload
sudo systemctl enable --now fermentlogcollector
```

## Development Quick Start

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn ferment_log_collector.main:app --reload
```

## Notes

- The seed device is `TresFermTrack-1`, disabled until you edit its base URL.
- Use the device IP address for the Base URL, for example
  `http://192.168.1.50`. Hostnames ending in `.local` rely on mDNS/Bonjour and
  may resolve slowly or fail from the collector process even when they work in a
  browser.
- Device files are stored by stable slug, for example
  `logs/devices/tresfermtrack-1/`.
- HTTP 404 from `/glycol_log.archived.csv` is treated as a normal "no archive
  yet" state.
- `/glycol_log.csv` can be fetched on demand as a live snapshot from the UI.
- Audit logs are plain text and rotate monthly under `logs/collector/`.
- This repository is only the remote collector. It does not include firmware
  changes.
