from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re
import sqlite3

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .collector import Collector
from .config import data_dir, database_path
from .db import Database
from .health import check_devices_health
from .storage import CollectorStorage
from .version import app_version


BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = app_version()
STATIC_ASSET_VERSION = str(
    max(
        (BASE_DIR / "static" / "styles.css").stat().st_mtime_ns,
        (BASE_DIR / "static" / "app.js").stat().st_mtime_ns,
    )
)
template_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
)
templates = Jinja2Templates(env=template_env)
db = Database(database_path())
storage = CollectorStorage(data_dir())
collector = Collector(db, storage)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    await collector.start()
    try:
        yield
    finally:
        await collector.stop()


app = FastAPI(title="FermentLogCollector", version=APP_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def index(request: Request):
    devices = db.list_devices_with_status()
    device_models = [device for device, _ in devices]
    health_by_device = await check_devices_health(device_models, storage)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "devices": devices,
            "health_by_device": health_by_device,
            "data_dir": str(data_dir()),
            "logs_dir": str(storage.logs_root),
            "app_version": APP_VERSION,
            "static_asset_version": STATIC_ASSET_VERSION,
            "flash": flash_from_request(request),
            "show_add_device": not devices,
        },
    )


@app.post("/devices")
async def create_device(
    name: str = Form(...),
    slug: str = Form(""),
    base_url: str = Form(...),
    polling_interval_seconds: int = Form(300),
    enabled: str | None = Form(None),
):
    try:
        db.upsert_device(
            name=name.strip(),
            slug=normalize_slug(slug or name),
            base_url=base_url.strip(),
            polling_interval_seconds=max(polling_interval_seconds, 10),
            enabled=enabled == "on",
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Device name or slug already exists") from exc
    return RedirectResponse("/", status_code=303)


@app.post("/devices/{device_id}")
async def update_device(
    device_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    base_url: str = Form(...),
    polling_interval_seconds: int = Form(300),
    enabled: str | None = Form(None),
):
    if db.get_device(device_id) is None:
        raise HTTPException(status_code=404)
    try:
        db.upsert_device(
            device_id=device_id,
            name=name.strip(),
            slug=normalize_slug(slug),
            base_url=base_url.strip(),
            polling_interval_seconds=max(polling_interval_seconds, 10),
            enabled=enabled == "on",
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Device name or slug already exists") from exc
    return RedirectResponse("/", status_code=303)


@app.post("/devices/{device_id}/delete")
async def delete_device(device_id: int):
    db.delete_device(device_id)
    return RedirectResponse("/", status_code=303)


@app.post("/devices/{device_id}/poll")
async def poll_now(device_id: int):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)
    await collector.poll_device(device)
    _, status = device_with_status(device_id)
    if status.last_error:
        flash = "archive-error"
    elif status.last_http_status == 404:
        flash = "archive-missing"
    else:
        flash = "archive-complete"
    return RedirectResponse(f"/?flash={flash}#device-{device_id}", status_code=303)


@app.post("/devices/{device_id}/live-snapshot")
async def live_snapshot(device_id: int):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)
    succeeded, _ = await collector.fetch_live_snapshot(device)
    flash = "live-complete" if succeeded else "live-error"
    return RedirectResponse(f"/?flash={flash}#device-{device_id}", status_code=303)


@app.get("/devices/{device_id}/combined.csv")
async def download_combined(device_id: int):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)
    path = storage.combined_csv_path(device)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Combined CSV not created yet")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/devices/{device_id}/latest-archive.csv")
async def download_latest_archive(device_id: int):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)
    stored_path = next((status.latest_archive_path for item, status in db.list_devices_with_status() if item.id == device_id), None)
    path = Path(stored_path) if stored_path else storage.latest_archive_path(device)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="No raw archive collected yet")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/devices/{device_id}/live.csv")
async def download_live_snapshot(device_id: int):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)
    path = storage.live_snapshot_path(device)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No live snapshot saved yet")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/api/devices/{device_id}/logs/{log_name}")
async def device_log_preview(device_id: int, log_name: str, tail: int = Query(100, ge=1, le=1000)):
    device = db.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404)

    if log_name == "combined":
        path = storage.combined_csv_path(device)
        missing_detail = "Combined CSV not created yet"
    elif log_name == "latest-archive":
        stored_path = next(
            (status.latest_archive_path for item, status in db.list_devices_with_status() if item.id == device_id),
            None,
        )
        path = Path(stored_path) if stored_path else storage.latest_archive_path(device)
        missing_detail = "No raw archive collected yet"
    elif log_name == "live":
        path = storage.live_snapshot_path(device)
        missing_detail = "No live snapshot saved yet"
    else:
        raise HTTPException(status_code=404, detail="Unknown device log")

    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=missing_detail)

    preview = storage.csv_preview(path, tail)
    preview["kind"] = "csv"
    preview["name"] = log_name
    return preview


@app.get("/audit/current.log")
async def download_current_audit():
    path = storage.current_audit_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="No audit log yet")
    return FileResponse(path, media_type="text/plain", filename=path.name)


@app.get("/api/audit/current")
async def current_audit_preview(tail: int = Query(100, ge=1, le=1000)):
    path = storage.current_audit_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="No audit log yet")

    preview = storage.text_tail(path, tail)
    preview["kind"] = "text"
    preview["name"] = "audit"
    return preview


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(BASE_DIR / "static" / "favicon.png", media_type="image/png")


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    if not slug:
        raise HTTPException(status_code=400, detail="Slug cannot be empty")
    return slug


def device_with_status(device_id: int):
    match = next(((device, status) for device, status in db.list_devices_with_status() if device.id == device_id), None)
    if match is None:
        raise HTTPException(status_code=404)
    return match


def flash_from_request(request: Request) -> dict[str, str] | None:
    messages = {
        "archive-complete": {
            "level": "success",
            "message": "Archive collection completed. Device status has been refreshed.",
        },
        "archive-missing": {
            "level": "notice",
            "message": "Archive collection completed, but this device has no archived log available yet.",
        },
        "archive-error": {
            "level": "error",
            "message": "Archive collection failed. Review the device error below.",
        },
        "live-complete": {
            "level": "success",
            "message": "Current data saved. Device status has been refreshed.",
        },
        "live-error": {
            "level": "error",
            "message": "Current data collection failed. Review the device error below.",
        },
    }
    return messages.get(request.query_params.get("flash", ""))
