from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def render_index(*, show_add_device: bool) -> str:
    template_dir = Path(__file__).parent.parent / "ferment_log_collector" / "templates"
    environment = Environment(loader=FileSystemLoader(template_dir))
    return environment.get_template("index.html").render(
        app_version="0.2.0",
        devices=[],
        health_by_device={},
        data_dir="data",
        logs_dir="logs",
        show_add_device=show_add_device,
        static_asset_version="test-assets",
    )


class ElementsByIdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attributes: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, _: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.attributes[element_id] = attributes


def elements_by_id(rendered: str) -> dict[str, dict[str, str | None]]:
    parser = ElementsByIdParser()
    parser.feed(rendered)
    return parser.attributes


def test_add_device_panel_is_open_for_empty_installation():
    rendered = render_index(show_add_device=True)
    elements = elements_by_id(rendered)

    assert elements["add-device-open"]["aria-expanded"] == "true"
    assert "hidden" in elements["add-device-open"]
    assert "hidden" not in elements["add-device-panel"]
    assert elements["add-device-close"]["aria-label"] == "Close add device form"


def test_add_device_panel_is_hidden_when_devices_exist():
    rendered = render_index(show_add_device=False)
    elements = elements_by_id(rendered)

    assert elements["add-device-open"]["aria-expanded"] == "false"
    assert "hidden" not in elements["add-device-open"]
    assert "hidden" in elements["add-device-panel"]
