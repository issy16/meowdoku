// Boards kept on this device to play again (R11.16), signed in or not. A
// kept board is the puzzle alone, as Python hands it over in each view;
// opening one asks Python to check it and start it fresh. They're never
// sent to the player's account.

const BOARDS_KEY = "meowdoku-boards";  // R11.15
const MAX_BOARDS = 50;
const MAX_NAME = 60;

const boards = (() => {
  let hooks = null;  // from app.js: t(key, args), language(), board(), open(board)
  let note = null;   // the message under the list, as {key, args, error}, worded again on language changes
  let showing = false;
  const $ = (id) => document.getElementById(id);

  // Kept boards, newest first, as [{board, kept, name?}]; a damaged list reads as empty.
  function load() {
    try {
      const list = JSON.parse(localStorage.getItem(BOARDS_KEY) || "[]");
      return Array.isArray(list) ? list.filter((entry) => entry && typeof entry === "object") : [];
    } catch {
      return [];
    }
  }

  // Throws if the browser won't store it; callers say so (R11.10).
  function store(list) {
    localStorage.setItem(BOARDS_KEY, JSON.stringify(list));
  }

  // The player's own name for it, or when it was kept, in the player's language.
  function nameOf(entry) {
    if (typeof entry.name === "string" && entry.name) return entry.name;
    const kept = new Date(entry.kept);
    if (Number.isNaN(kept.getTime())) return "?";
    return new Intl.DateTimeFormat(hooks.language(), { dateStyle: "medium", timeStyle: "short" }).format(kept);
  }

  function say(key, args = {}, error = false) {
    note = key ? { key, args, error } : null;
    render();
  }

  function render() {
    if (!hooks) return;
    const list = load();
    const toggle = $("show-boards");
    toggle.textContent = hooks.t("ui.saved_boards", { count: list.length });
    toggle.setAttribute("aria-expanded", String(showing));
    const items = $("board-list");
    items.hidden = !showing;
    items.replaceChildren(...(list.length ? list.map(item) : [emptyItem()]));
    const line = $("boards-message");
    line.textContent = note ? hooks.t(note.key, note.args) : "";
    line.classList.toggle("error", Boolean(note && note.error));
  }

  function item(entry, index) {
    const row = document.createElement("li");
    const name = button(nameOf(entry), "board-name", () => open(index));
    row.append(name, button(hooks.t("ui.rename"), "link", () => rename(index)),
      button(hooks.t("ui.delete"), "link", () => remove(index)));
    return row;
  }

  function emptyItem() {
    const row = document.createElement("li");
    row.className = "empty";
    row.textContent = hooks.t("ui.no_boards");
    return row;
  }

  function button(text, className, onclick) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = className;
    element.textContent = text;
    element.onclick = onclick;
    return element;
  }

  function save() {
    const board = hooks.board();
    if (!board) return;
    const list = load();
    if (list.length >= MAX_BOARDS) { say("ui.boards_full", { max: MAX_BOARDS }, true); return; }
    try {
      store([{ board, kept: new Date().toISOString() }, ...list]);
      say("ui.board_saved");
    } catch {
      say("ui.board_save_failed", {}, true);
    }
  }

  // Opens as a fresh game, replacing the current one; a bad board is refused by Python with a message.
  async function open(index) {
    const entry = load()[index];
    if (!entry) return;
    showing = false;
    say(null);
    await hooks.open(entry.board);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function rename(index) {
    const list = load();
    const entry = list[index];
    if (!entry) return;
    const typed = prompt(hooks.t("ui.rename_prompt"), nameOf(entry));
    if (typed === null) return;
    const name = typed.trim().slice(0, MAX_NAME);
    if (name) entry.name = name;
    else delete entry.name;  // an empty name goes back to the date
    change(list);
  }

  function remove(index) {
    const list = load();
    const entry = list[index];
    if (!entry || !confirm(hooks.t("ui.delete_board_confirm", { name: nameOf(entry) }))) return;
    list.splice(index, 1);
    change(list);
  }

  function change(list) {
    try {
      store(list);
      say(null);
    } catch {
      say("ui.board_save_failed", {}, true);
    }
  }

  function start(appHooks) {
    hooks = appHooks;
    $("save-board").onclick = save;
    $("show-boards").onclick = () => {
      showing = !showing;
      say(null);
    };
    render();
  }

  return { start, render };
})();
