# New Chat Prompt: FermentLogCollector

Use this prompt to start a new Codex task in a separate project/repository.

```text
I want to create a new project named FermentLogCollector.

This must be separate from my brewpi-esp firmware repository. Do not add host-side
collector code to brewpi-esp.

Goal:
Build a small local web service that collects glycol event logs from one or more
BrewPi-ESP devices. The first device is named TresFermTrack-1.

Context:
BrewPi-ESP writes a glycol event CSV to /glycol_log.csv. We plan to modify the
firmware so it also keeps /glycol_log.archived.csv as the most recent completed
segment. The collector should periodically fetch the archived CSV, hash it,
deduplicate it, save the raw archive, and append only new data rows to a long
combined CSV.

Please read and follow these two source documents from the brewpi-esp repo:

- docs/FermentLogCollector_HANDOFF.md
- docs/BREWPI_ESP_GLYCOL_ARCHIVED_LOG_SPEC.md

Build the first version using a simple stack:

- Python 3
- FastAPI
- SQLite
- Jinja2 or HTMX for the GUI
- httpx for polling
- plain text monthly audit logs

Core requirements:

- multi-device support;
- create/edit/delete devices;
- enable/disable collection per device;
- configurable base URL and polling interval;
- periodic polling of /glycol_log.archived.csv;
- graceful handling of 404 before the first archive exists;
- SHA-256 dedupe;
- raw archive storage;
- combined CSV per device with only one header;
- optional live snapshot fetch from /glycol_log.csv;
- human-readable collector audit log rotated monthly;
- web GUI showing device status, last fetch, last success, last new archive,
  errors, rows collected, and download links.

Do not implement firmware changes in this project. Only build the remote
collector.
```

