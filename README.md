# FermentLogCollector

Small local FastAPI service that collects BrewPi-ESP glycol log archive segments.

The collector polls each enabled device at `/glycol_log.archived.csv`, hashes the
CSV with SHA-256, deduplicates already-seen archives, stores the raw archive, and
appends only new data rows to a long per-device combined CSV.

## Quick Start

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn ferment_log_collector.main:app --reload
```

Open http://127.0.0.1:8000.

The app creates its SQLite database under `data/` and collected logs under
`logs/` by default. Override the data directory with:

```sh
FERMENT_COLLECTOR_DATA_DIR=/path/to/data uvicorn ferment_log_collector.main:app
```

## Notes

- The seed device is `TresFermTrack-1`, disabled until you edit its base URL.
- Device files are stored by stable slug, for example
  `logs/devices/tresfermtrack-1/`.
- HTTP 404 from `/glycol_log.archived.csv` is treated as a normal "no archive
  yet" state.
- `/glycol_log.csv` can be fetched on demand as a live snapshot from the UI.
- Audit logs are plain text and rotate monthly under `logs/collector/`.
- This repository is only the remote collector. It does not include firmware
  changes.
