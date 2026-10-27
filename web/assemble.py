"""Put the web app's files together in one folder, ready to publish (R11.13).

    python web/assemble.py OUT          write the site into OUT
    python web/assemble.py --serve      serve it at http://localhost:8000/meowdoku/

The folder holds the page, its styles and scripts, meowdoku.zip (the Python
package plus timings.py, which the web worker unpacks), and a sample
screenshot. GitHub Pages publishes it at https://issy16.github.io/meowdoku/,
so --serve puts it under /meowdoku/ too, and path mistakes show up locally
(R11.14). Standard library only.
"""

import argparse
import functools
import http.server
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
PACKAGE = ROOT / "src" / "meowdoku"
SAMPLE = ROOT / "tests" / "fixtures" / "screenshots" / "IMG_7117.PNG"

PAGE_FILES = ("index.html", "style.css", "app.js", "worker.js")
SKIPPED_MODULES = {"gui.py", "cli.py", "__main__.py"}  # desktop and command line only
SUBPATH = "meowdoku"


def package_files() -> list[Path]:
    """The package's modules the browser needs, in a stable order."""
    return sorted(path for path in PACKAGE.glob("*.py") if path.name not in SKIPPED_MODULES)


def write_zip(target: Path) -> None:
    """meowdoku/*.py and timings.py, with fixed timestamps so the zip is the same each time (NFR4)."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        entries = [(path, f"meowdoku/{path.name}") for path in package_files()]
        entries.append((WEB / "timings.py", "timings.py"))
        for source, name in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())


def assemble(out: Path) -> Path:
    """Write the site into `out` (created if needed) and return it."""
    out.mkdir(parents=True, exist_ok=True)
    for name in PAGE_FILES:
        shutil.copyfile(WEB / name, out / name)
    shutil.copyfile(SAMPLE, out / "sample.png")
    write_zip(out / "meowdoku.zip")
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the site, assembling it again whenever the page loads, so edits show on reload."""

    def do_GET(self) -> None:
        if self.path.split("?")[0] in (f"/{SUBPATH}/", f"/{SUBPATH}/index.html"):
            assemble(Path(self.directory) / SUBPATH)
        super().do_GET()


def serve(port: int) -> None:
    """Serve the site at /meowdoku/ until stopped."""
    with tempfile.TemporaryDirectory() as root:
        assemble(Path(root) / SUBPATH)
        handler = functools.partial(Handler, directory=root)
        with http.server.ThreadingHTTPServer(("localhost", port), handler) as server:
            print(f"Serving http://localhost:{port}/{SUBPATH}/  (Ctrl+C to stop)", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", nargs="?", type=Path, help="folder to write the site into")
    parser.add_argument("--serve", action="store_true", help="serve it at /meowdoku/ instead")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.serve:
        serve(args.port)
    elif args.out is not None:
        print(assemble(args.out))
    else:
        parser.error("give a folder, or --serve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
