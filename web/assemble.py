"""Put the web app's files together in one folder, ready to publish (R11.13).

    python web/assemble.py OUT          write the site into OUT
    python web/assemble.py --serve      serve it at http://localhost:8000/meowdoku/

The folder holds the page, its styles and scripts, meowdoku.zip (the Python
package plus timings.py, which the web worker unpacks), labels.json (the
page's wording in every language, from meowdoku/messages.py, R12.1), and a
sample screenshot. GitHub Pages publishes it at https://issy16.github.io/meowdoku/,
so --serve puts it under /meowdoku/ too, and path mistakes show up locally
(R11.14). Standard library only.
"""

import argparse
import functools
import hashlib
import importlib
import http.server
import json
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


def write_labels(target: Path, fresh: bool = False) -> None:
    """The page's wording in every language, so it can show "Loading…" before Python starts.

    `fresh` reads messages.py again, so --serve shows edits on reload; only the
    server does that, since other modules keep using the module they imported.
    """
    sys.path.insert(0, str(PACKAGE.parent))
    import meowdoku.messages

    messages = importlib.reload(meowdoku.messages) if fresh else meowdoku.messages
    data = {"languages": messages.LANGUAGES, "labels": {code: messages.labels(code) for code in messages.LANGUAGES}}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1))


STAMPED = ("style.css", "app.js", "worker.js", "labels.json", "meowdoku.zip")
"""Files the page loads by name; each release asks for them as name?v=<version>."""
REFERRERS = ("index.html", "app.js", "worker.js")


def stamp(out: Path) -> str:
    """Make the page ask for this release's own files, so a browser never mixes in cached old ones.

    GitHub Pages lets browsers keep files for 10 minutes. Adding ?v=<version>
    to each reference, where the version comes from the files' contents, makes
    a new page fetch new scripts at once. Returns the version.
    """
    digest = hashlib.sha256()
    for name in STAMPED + REFERRERS:
        digest.update((out / name).read_bytes())
    version = digest.hexdigest()[:10]
    for name in REFERRERS:
        text = (out / name).read_text()
        for stamped in STAMPED:
            text = text.replace(f'"{stamped}"', f'"{stamped}?v={version}"')
        (out / name).write_text(text)
    return version


def assemble(out: Path, fresh: bool = False) -> Path:
    """Write the site into `out` (created if needed) and return it."""
    out.mkdir(parents=True, exist_ok=True)
    for name in PAGE_FILES:
        shutil.copyfile(WEB / name, out / name)
    shutil.copyfile(SAMPLE, out / "sample.png")
    write_zip(out / "meowdoku.zip")
    write_labels(out / "labels.json", fresh)
    stamp(out)
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the site, assembling it again whenever the page loads, so edits show on reload."""

    def do_GET(self) -> None:
        if self.path.split("?")[0] in (f"/{SUBPATH}/", f"/{SUBPATH}/index.html"):
            assemble(Path(self.directory) / SUBPATH, fresh=True)
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
