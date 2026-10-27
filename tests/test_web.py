"""The web app's files: what gets published, and paths that work under /meowdoku/ (R11.13, R11.14)."""

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType

from meowdoku.messages import LANGUAGES, labels

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SAMPLE = ROOT / "tests" / "fixtures" / "screenshots" / "IMG_7117.PNG"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, WEB / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


assemble = load("assemble")
timings = load("timings")

# A path the browser would resolve from the site root, like "/app.js", in
# src= or href=, url(), fetch(), new Worker(), or importScripts().
ROOT_PATH = re.compile(
    r"""(?:\b(?:src|href)\s*=\s*["']|url\(\s*["']?|\b(?:fetch|Worker|importScripts|import)\(\s*["']|\bfrom\s+["'])/(?!/)"""
)


def test_r11_14_no_web_file_loads_from_the_site_root() -> None:
    files = [path for path in WEB.iterdir() if path.suffix in {".html", ".css", ".js"}]
    assert files
    for path in files:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            assert not ROOT_PATH.search(line), f"{path.name}:{number} starts a path with /"


def test_r11_14_root_path_check_catches_mistakes() -> None:
    for line in ('<script src="/app.js">', "fetch('/meowdoku.zip')", "url(/a.png)", 'new Worker("/worker.js")',
                 'import { x } from "/x.mjs";'):
        assert ROOT_PATH.search(line), line
    for line in ('<script src="app.js">', 'importScripts("https://cdn.jsdelivr.net/x.js")', '<use href="#cat"/>'):
        assert not ROOT_PATH.search(line), line


def test_r11_1_pyodide_is_pinned() -> None:
    """NFR6: one exact Pyodide release, from jsDelivr."""
    worker = (WEB / "worker.js").read_text()
    assert set(re.findall(r"https://cdn\.jsdelivr\.net/pyodide/v[\d.]+/full/", worker)) == {
        "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"
    }


def test_r11_13_assemble_writes_the_site(tmp_path: Path) -> None:
    out = assemble.assemble(tmp_path / "site")
    assert sorted(path.name for path in out.iterdir()) == [
        "app.js", "index.html", "labels.json", "meowdoku.zip", "sample.png", "style.css", "worker.js",
    ]
    with zipfile.ZipFile(out / "meowdoku.zip") as archive:
        names = archive.namelist()
    assert "meowdoku/bridge.py" in names and "timings.py" in names
    assert "meowdoku/gui.py" not in names  # tkinter isn't in the browser


def test_r11_13_zip_is_the_same_each_time(tmp_path: Path) -> None:
    assemble.write_zip(tmp_path / "a.zip")
    assemble.write_zip(tmp_path / "b.zip")
    assert (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()


def test_r11_12_measure_reports_timings() -> None:
    rows = {key: value for key, _, value in json.loads(timings.measure(str(SAMPLE)))}
    assert isinstance(rows["timing.import"], int)
    assert isinstance(rows["timing.solve"], int)
    assert "timing.slowest_d6" in rows
    assert rows["timing.solved_by_hints"] in {"timing.yes", "timing.no"}
    every_key = set(rows) | {value for value in rows.values() if isinstance(value, str)}
    assert every_key <= set(labels("en"))


def test_r12_1_labels_json_has_every_language(tmp_path: Path) -> None:
    out = assemble.assemble(tmp_path / "site")
    data = json.loads((out / "labels.json").read_text())
    assert list(data["languages"]) == list(LANGUAGES)
    for code in LANGUAGES:
        assert set(data["labels"][code]) == set(labels("en"))
        assert all(data["labels"][code].values())


def test_r12_1_page_uses_only_known_labels() -> None:
    """Every label the page asks for exists, so nothing shows up as a bare key."""
    page = (WEB / "app.js").read_text() + (WEB / "index.html").read_text() + (WEB / "worker.js").read_text()
    used = set(re.findall(r"\b((?:ui|timing)\.[a-z_]+)\b", page))
    assert used
    assert used <= set(labels("en"))


def test_r12_1_every_button_is_worded_before_python_loads() -> None:
    """Labels come from labels.json, so even while loading nothing shows in English by mistake."""
    page = (WEB / "index.html").read_text()
    buttons = re.findall(r"<button\b[^>]*>", page)
    assert buttons
    for button in buttons:
        assert "data-label=" in button or "data-name=" in button, button


def test_r11_7a_each_release_asks_for_its_own_files(tmp_path: Path) -> None:
    """A browser's cached old app.js can't run with a new page: every reference carries the release's version."""
    out = assemble.assemble(tmp_path / "site")
    page = (out / "index.html").read_text() + (out / "app.js").read_text() + (out / "worker.js").read_text()
    versions = set(re.findall(r'"(?:style\.css|app\.js|worker\.js|labels\.json|meowdoku\.zip)\?v=(\w+)"', page))
    assert len(versions) == 1
    for name in assemble.STAMPED:
        assert f'"{name}"' not in page  # nothing left unstamped
    assert not ROOT_PATH.search(page)


def test_r11_7a_the_version_changes_with_the_files(tmp_path: Path) -> None:
    first = assemble.assemble(tmp_path / "a")
    second = assemble.assemble(tmp_path / "b")
    assert (first / "index.html").read_text() == (second / "index.html").read_text()  # same files, same version
    (second / "app.js").write_text("changed")
    for name in assemble.PAGE_FILES:
        if name != "app.js":
            (second / name).write_text((assemble.WEB / name).read_text())
    assert assemble.stamp(second) != re.search(r"\?v=(\w+)", (first / "index.html").read_text()).group(1)
