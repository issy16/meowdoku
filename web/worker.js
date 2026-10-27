// Runs Python off the page's main thread (R11.3): loads Pyodide, Pillow, and
// the meowdoku package, then answers the page's actions through bridge.py.
// Messages in: {id, action, args} or {id, action: "open", name, bytes}.
// Messages out: {type: "ready", timings}, {id, view, ms}, or {id, failure}.

// A module worker: some browsers refuse importScripts() from another site.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";  // pinned (NFR6)
const PACKAGE_DIR = "/home/pyodide/app";

let pyodide = null;
let handle = null;
let measure = null;

async function timed(timings, name, step) {
  const start = performance.now();
  const result = await step();
  timings.push([name, Math.round(performance.now() - start)]);
  return result;
}

async function start() {
  const timings = [];
  // Rows are named by label key; the page words them (R12.1).
  pyodide = await timed(timings, "timing.start", () => loadPyodide({ indexURL: PYODIDE_URL }));
  await timed(timings, "timing.pillow", () => pyodide.loadPackage("pillow"));
  await timed(timings, "timing.package", async () => {
    // Relative to this script, so it works under /meowdoku/ (R11.14).
    const zip = await fetch("meowdoku.zip");
    if (!zip.ok) throw new Error(`meowdoku.zip: HTTP ${zip.status}`);
    pyodide.unpackArchive(await zip.arrayBuffer(), "zip", { extractDir: PACKAGE_DIR });
    pyodide.runPython(`
import sys
sys.path.insert(0, "${PACKAGE_DIR}")
from meowdoku.bridge import Bridge
import timings
bridge = Bridge()
`);
    handle = pyodide.globals.get("bridge").handle;
    measure = pyodide.globals.get("timings").measure;
  });
  return timings;
}

function answer(message) {
  const start = performance.now();
  let args = message.args || [];
  if (message.action === "open" || message.action === "measure") {
    // The screenshot stays on this device: it goes only into Pyodide's in-memory files (R11.5),
    // under the player's own file name, so errors can name it.
    const name = message.name.split(/[\\/]/).pop() || "screenshot";
    pyodide.FS.mkdirTree("/tmp/upload");
    const path = "/tmp/upload/" + name;
    pyodide.FS.writeFile(path, new Uint8Array(message.bytes));
    args = [path];
  }
  if (message.action === "measure") {
    const rows = JSON.parse(measure(args[0]));
    return { id: message.id, rows, ms: Math.round(performance.now() - start) };
  }
  const view = JSON.parse(handle(JSON.stringify({ action: message.action, args })));
  return { id: message.id, view, ms: Math.round(performance.now() - start) };
}

const ready = start();

ready.then(
  (timings) => postMessage({ type: "ready", timings }),
  (error) => postMessage({ type: "failed", failure: String(error) }),
);

// Python runs one action at a time, in the order the page sent them.
let queue = ready;
onmessage = (event) => {
  queue = queue.then(() => {
    try {
      postMessage(answer(event.data));
    } catch (error) {
      postMessage({ id: event.data.id, failure: String(error) });
    }
  }, () => {});
};
