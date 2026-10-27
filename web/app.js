// The page: draws the board description the worker sends and forwards taps,
// drags, and buttons to it. No game logic lives here (R11.2).

const MAX_BYTES = 20 * 1024 * 1024;  // R11.5
const MAX_SIDE = 8000;
const DOUBLE_TAP_MS = 350;
const BUSY_AFTER_MS = 150;
const LANGUAGE_KEY = "meowdoku-language";  // R11.15, R12.3
const THEME_KEY = "meowdoku-theme";  // R13.3
const THEMES = { auto: "ui.theme_auto", light: "ui.theme_light", night: "ui.theme_night" };  // in button order

const $ = (id) => document.getElementById(id);
const board = $("board");
const statusLine = $("status");
const messageLine = $("message");

// Relative to the page, so it works under /meowdoku/ (R11.14).
const worker = new Worker("worker.js", { type: "module" });
let ready = false;
let nextId = 1;
const pending = new Map();
let view = null;
let tiles = [];

// Buttons wait for Python, so a press is never silently dropped while it loads.
const controls = document.querySelectorAll("main button:not(#theme)");
controls.forEach((button) => { button.disabled = true; });

// ---- Languages (R12) -------------------------------------------------------
// labels.json holds the page's wording in every language, made from
// meowdoku/messages.py; hints and errors come from Python already worded.

let wording = { languages: { en: "English" }, labels: { en: {} } };
let language = "en";
let loadProblem = null;  // why the game couldn't load, shown in the chosen language

function t(key, args = {}) {
  const template = (wording.labels[language] || {})[key] ?? (wording.labels.en || {})[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(args[name] ?? ""));
}

function stored(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function remember(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private window: the choice lasts this visit */ }
}

// ---- Night mode (R13) --------------------------------------------------------
// Auto leaves the look to the device (CSS prefers-color-scheme); Light and
// Night set data-theme on the page, which the styles follow.

let theme = stored(THEME_KEY) in THEMES ? stored(THEME_KEY) : "auto";

function applyTheme() {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  const button = $("theme");
  button.dataset.choice = theme;
  button.dataset.name = THEMES[theme];
  const name = t("ui.appearance_choice", { choice: t(THEMES[theme]) });
  button.setAttribute("aria-label", name);
  button.title = name;
}

$("theme").onclick = () => {
  const order = Object.keys(THEMES);
  theme = order[(order.indexOf(theme) + 1) % order.length];
  remember(THEME_KEY, theme);
  applyTheme();
};
applyTheme();

// The first of the browser's languages the app offers, or null; any Chinese is zh-TW (R12.3).
function browserLanguage() {
  for (const code of navigator.languages || [navigator.language || "en"]) {
    const lower = code.toLowerCase();
    if (lower.startsWith("zh")) return "zh-TW";
    const match = Object.keys(wording.languages).find((offered) => offered.toLowerCase() === lower.split("-")[0]);
    if (match) return match;
  }
  return null;
}

function applyLabels() {
  document.documentElement.lang = language;
  document.querySelectorAll("[data-label]").forEach((element) => { element.textContent = t(element.dataset.label); });
  // Icon buttons (undo and redo arrows) keep their name for screen readers and as a tooltip.
  document.querySelectorAll("[data-name]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.name));
    element.title = t(element.dataset.name);
  });
  applyTheme();
  $("language").value = language;
  if (!ready) statusLine.textContent = loadProblem ? t("ui.load_failed", { reason: loadProblem }) : t("ui.loading");
  renderTimings();
  if (view) show(view);
}

function chooseLanguage(code) {
  language = code in wording.languages ? code : "en";
  applyLabels();
  if (ready) act("language", language);
}

async function loadWording() {
  try {
    const response = await fetch("labels.json");
    if (response.ok) wording = await response.json();
  } catch { /* keep English */ }
  // The browser's own language first in the menu, then the rest (R12.2).
  const own = browserLanguage();
  const codes = Object.keys(wording.languages);
  const ordered = own ? [own, ...codes.filter((code) => code !== own)] : codes;
  $("language").replaceChildren(...ordered.map((code) => new Option(wording.languages[code], code)));
  const saved = stored(LANGUAGE_KEY);
  language = saved && saved in wording.languages ? saved : own || "en";
  applyLabels();
}

$("language").onchange = () => {
  remember(LANGUAGE_KEY, $("language").value);
  chooseLanguage($("language").value);
};

const wordingLoaded = loadWording();

// ---- Talking to the worker -------------------------------------------------

function send(message, transfer = []) {
  if (!ready) return Promise.resolve(null);
  const id = nextId++;
  const promise = new Promise((resolve) => pending.set(id, resolve));
  worker.postMessage({ ...message, id }, transfer);
  setTimeout(() => { if (pending.has(id)) statusLine.classList.add("busy"); }, BUSY_AFTER_MS);
  return promise;
}

async function act(action, ...args) {
  const reply = await send({ action, args });
  if (reply && reply.view) show(reply.view, action, reply.ms);
}

worker.onmessage = (event) => {
  const data = event.data;
  if (data.type === "ready") {
    wordingLoaded.then(() => {
      ready = true;
      controls.forEach((button) => { button.disabled = false; });
      data.timings.forEach(([key, ms]) => noteTiming(key, ms));
      statusLine.textContent = "";
      act("language", language);
    });
    return;
  }
  if (data.type === "failed") {
    loadProblem = data.failure;
    applyLabels();
    return;
  }
  const resolve = pending.get(data.id);
  pending.delete(data.id);
  if (pending.size === 0) statusLine.classList.remove("busy");
  if (data.failure) {
    showError(t("ui.went_wrong_reason", { reason: data.failure }));
    resolve(null);
    return;
  }
  resolve(data);
};

worker.onerror = (event) => {
  loadProblem = event.message || "worker.js";
  applyLabels();
};

// ---- Drawing ---------------------------------------------------------------

const has = (cells, row, col) => cells.some(([r, c]) => r === row && c === col);

function buildBoard(size) {
  board.style.setProperty("--n", size);
  board.replaceChildren();
  tiles = [];
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.dataset.row = row;
      tile.dataset.col = col;
      board.append(tile);
      tiles.push(tile);
    }
  }
}

const CROSS = '<svg class="cross" viewBox="0 0 10 10"><path d="M1 1L9 9M1 9L9 1" stroke-width="2.2"/></svg>';
const CAT = '<svg viewBox="0 0 100 100"><use href="#cat"/></svg>';

function show(next, action, ms) {
  const rebuild = !view || view.size !== next.size || view.regions.join() !== next.regions.join();
  view = next;
  if (rebuild) buildBoard(view.size);
  if (action) noteTiming("ui.last_action", `${action}, ${ms} ms`);

  for (const tile of tiles) {
    const row = +tile.dataset.row;
    const col = +tile.dataset.col;
    tile.style.background = view.colors[view.regions[row][col]];
    let content = "";
    if (has(view.cats, row, col)) content = CAT;
    else if (has(view.crosses, row, col)) content = CROSS;
    else if (has(view.solution, row, col)) content = `<span class="revealed">${CAT}</span>`;
    if (tile.dataset.content !== content) {
      tile.innerHTML = content;
      tile.dataset.content = content;
    }
    const lit = has(view.highlight, row, col);
    tile.classList.toggle("ring", lit);
    tile.classList.toggle("problem", lit && view.highlight_style === "problem");
  }

  const fresh = action && action !== "language";  // a new move, not the same board reworded
  if (view.shake && fresh) shake(view.shake);
  showMessage();
  $("previous").disabled = !ready || !view.can_undo;
  $("next").disabled = !ready || !view.can_redo;
  $("step").textContent = t(view.stepping ? "ui.next_step" : "ui.step");  // R8.12
  if (view.just_solved && fresh) $("popup").hidden = false;
}

function shake([row, col]) {
  const tile = tiles[row * view.size + col];
  tile.classList.remove("shake");
  void tile.offsetWidth;  // restart the animation
  tile.classList.add("shake");
}

function showMessage() {
  messageLine.classList.toggle("error", Boolean(view.error));
  messageLine.textContent = view.error || view.message;
  messageLine.scrollTop = 0;  // each new message starts at its first line
  if (!view.error && view.can_apply) {
    const apply = document.createElement("button");
    apply.className = "link";
    apply.type = "button";
    apply.textContent = t("ui.apply");
    apply.onclick = () => act("apply");
    messageLine.append(" ", apply);
  }
}

function showError(text) {
  messageLine.classList.add("error");
  messageLine.textContent = text;
}

// Timings rows by label key, worded again whenever the language changes.
const timings = new Map();
function noteTiming(key, value, args = {}) {
  timings.set(key, { value, args });
  renderTimings();
}

function renderTimings() {
  $("timings").replaceChildren(...[...timings].map(([key, { value, args }]) => {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    const shown = document.createElement("td");
    name.textContent = t(key, args);
    shown.textContent = typeof value === "number" ? `${value} ms`
      : value.startsWith("timing.") ? t(value) : value;
    row.append(name, shown);
    return row;
  }));
}

// ---- Taps, double taps, and drags (R11.1a) ---------------------------------

let pressed = null;      // the cell under the pointer while it's down
let lastTap = null;      // {row, col, time} of the last press, for double taps
let doubled = false;     // this press was a double tap: its release isn't a click

function cellAt(x, y) {
  const rect = board.getBoundingClientRect();
  if (!view || x < rect.left || y < rect.top || x >= rect.right || y >= rect.bottom) return null;
  const row = Math.floor(((y - rect.top) / rect.height) * view.size);
  const col = Math.floor(((x - rect.left) / rect.width) * view.size);
  return { row, col };
}

board.addEventListener("pointerdown", (event) => {
  if (!event.isPrimary) return;
  const cell = cellAt(event.clientX, event.clientY);
  if (!cell) return;
  event.preventDefault();
  board.setPointerCapture(event.pointerId);
  const now = performance.now();
  doubled = Boolean(lastTap && lastTap.row === cell.row && lastTap.col === cell.col
    && now - lastTap.time < DOUBLE_TAP_MS);
  lastTap = doubled ? null : { ...cell, time: now };
  pressed = cell;
  if (doubled) act("double", cell.row, cell.col);
  else act("press", cell.row, cell.col);
});

board.addEventListener("pointermove", (event) => {
  if (!pressed || doubled || !event.isPrimary) return;
  const cell = cellAt(event.clientX, event.clientY);
  if (!cell || (cell.row === pressed.row && cell.col === pressed.col)) return;
  pressed = cell;
  lastTap = null;
  act("move", cell.row, cell.col);
});

function release(event) {
  if (!pressed || !event.isPrimary) return;
  const cell = cellAt(event.clientX, event.clientY) || { row: -1, col: -1 };
  pressed = null;
  if (doubled) { doubled = false; return; }
  act("release", cell.row, cell.col);
}
board.addEventListener("pointerup", release);
board.addEventListener("pointercancel", release);

// ---- Buttons ---------------------------------------------------------------

$("previous").onclick = () => act("previous");
$("next").onclick = () => act("next");
$("hint").onclick = () => act("hint");
$("step").onclick = () => act("step");
$("solve").onclick = () => act("solve");
$("reset").onclick = () => act("reset");
$("open").onclick = () => $("file").click();

$("file").onchange = async () => {
  const file = $("file").files[0];
  $("file").value = "";
  if (file) await openFile(file);
};

async function openFile(file) {
  const problem = await refusal(file);
  if (problem) { showError(problem); return; }
  const bytes = await file.arrayBuffer();
  const reply = await send({ action: "open", name: file.name, bytes }, [bytes]);
  if (reply && reply.view) {
    show(reply.view, "open", reply.ms);
    noteTiming("timing.import", reply.ms);
  }
}

// Screenshots must be PNG or JPEG, at most 20 MB and 8000 pixels a side (R11.5).
async function refusal(file) {
  if (!/\.(png|jpe?g)$/i.test(file.name) && !/^image\/(png|jpeg)$/.test(file.type)) {
    return t("ui.pick_png");
  }
  if (file.size > MAX_BYTES) return t("ui.too_big_bytes");
  try {
    const image = await createImageBitmap(file);
    const tooBig = image.width > MAX_SIDE || image.height > MAX_SIDE;
    image.close();
    if (tooBig) return t("ui.too_big_pixels", { max: MAX_SIDE });
  } catch {
    return t("ui.not_image");
  }
  return null;
}

async function sampleFile() {
  const response = await fetch("sample.png");
  return new File([await response.blob()], "sample.png", { type: "image/png" });
}

$("sample").onclick = async () => openFile(await sampleFile());

$("measure").onclick = async () => {
  const bytes = await (await sampleFile()).arrayBuffer();
  const reply = await send({ action: "measure", name: "sample.png", bytes }, [bytes]);
  if (reply && reply.rows) reply.rows.forEach(([key, args, value]) => noteTiming(key, value, args));
};

// ---- The solved pop-up (R8.6) ----------------------------------------------

function closePopup() { $("popup").hidden = true; }
$("popup").addEventListener("click", closePopup);
document.addEventListener("keydown", (event) => {
  if (!$("popup").hidden && (event.key === "Enter" || event.key === "Escape")) closePopup();
});
