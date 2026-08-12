from importlib import metadata
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ferment_log_collector.version import app_version


def test_app_version_comes_from_package_metadata(monkeypatch):
    requested_distribution = None

    def fake_version(distribution_name: str) -> str:
        nonlocal requested_distribution
        requested_distribution = distribution_name
        return "9.8.7"

    monkeypatch.setattr(metadata, "version", fake_version)

    assert app_version() == "9.8.7"
    assert requested_distribution == "ferment-log-collector"


def test_app_version_has_development_fallback(monkeypatch):
    def missing_distribution(_: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(metadata, "version", missing_distribution)

    assert app_version() == "0+development"


def test_index_template_renders_supplied_version():
    template_dir = Path(__file__).parent.parent / "ferment_log_collector" / "templates"
    environment = Environment(loader=FileSystemLoader(template_dir))

    rendered = environment.get_template("index.html").render(
        app_version="9.8.7",
        devices=[],
        health_by_device={},
        data_dir="data",
        logs_dir="logs",
    )

    assert '<span class="app-version" title="Application version">v9.8.7</span>' in rendered
