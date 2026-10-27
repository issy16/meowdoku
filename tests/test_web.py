"""The web app's files: what gets published, and paths that work under /meowdoku/ (R11.13, R11.14)."""

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType

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
        "app.js", "index.html", "meowdoku.zip", "sample.png", "style.css", "worker.js",
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
    rows = dict(json.loads(timings.measure(str(SAMPLE))))
    assert isinstance(rows["Screenshot import"], int)
    assert isinstance(rows["Solve (first time)"], int)
    assert "Slowest D6 hint" in rows
    assert rows["Solved by hints alone"] in {"yes", "no"}
