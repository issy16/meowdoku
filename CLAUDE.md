# CLAUDE.md

Guidance for AI assistants working in this repository.

## Project

Meowdoku Solver: a Python solver for Meowdoku puzzles (see README.md for the
rules). The owner reviews architecture and algorithm decisions before
implementation. **Do not implement features outside docs/requirements.md
without the owner's approval**, and work one approved milestone at a time.

## Stack constraints

- Python 3.11+, standard library only for code under `src/`, with one
  approved exception: Pillow, a regular dependency for reading screenshots.
  Only `image_import.py` imports it; the solver, rules, hints, and
  deduction stay standard library only.
- The GUI uses tkinter (standard library).
- The web app (R11) lives in `web/`: plain HTML, CSS, and JavaScript with
  no build step, running `src/meowdoku/` in the browser with a pinned
  Pyodide release. Its other tools (sign-in client, browser test tool,
  GitHub Pages actions) are added only once the owner approves each and it
  is named in NFR6.
- pytest is the only development dependency, plus PyInstaller as a
  build-only tool for the Mac app (the `[build]` extra, approved by the
  owner). Do not add packages (including Hypothesis) without written
  justification and owner approval.

## Web app rules

- It is published at `https://issy16.github.io/meowdoku/` from this
  repository. Never change, move, or delete the owner's résumé site
  (`https://issy16.github.io/`, a separate repository).
- Paths to the app's own files are relative to the page, never starting
  with `/`; nothing goes in the URL; test under a `/meowdoku/` folder
  (R11.14).
- Everything stored in the browser uses a `meowdoku` prefix (R11.15).
- No secret or privileged keys in `web/` or anywhere in the repository; the
  sign-in service enforces who can read each save (R11.9).
- Guest play always works; sign-in is optional (R11.6). Phones are
  supported (R11.1a).

## Commands

```bash
source .venv/bin/activate
python -m pytest          # run all tests; must pass before every commit
```

Serve the web app locally at http://localhost:8000/meowdoku/ (reassembled on
each page load), or write the site that GitHub Pages publishes:

```bash
python web/assemble.py --serve
python web/assemble.py _site
```

Build the shareable Mac app (writes `dist/`, which is not committed):

```bash
packaging/build.sh
```

## Architecture

```text
src/meowdoku/
  puzzle.py        Puzzle type, structural validation, error types
  parser.py        text grid -> Puzzle (internal and tests only), Puzzle + cats -> text
  rules.py         solution validator (find_violations)
  solver.py        backtracking search (iter_solutions, solve)
  state.py         BoardState: player's cats and ✕ marks
  deduce.py        deduction rules D1–D5 (see docs/algorithm.md)
  assume.py        D6: contradiction by assumption, built on D1–D5
  hints.py         next_hint: violations, mistakes, D1–D6 (never reveals answers)
  image_import.py  screenshot -> text grid, region colors, cats and ✕ marks (Pillow)
  colors.py        plain color names for regions ("the pink region")
  cli.py           thin command-line wrapper
  game.py          GameSession: GUI behavior (clicks, buttons, colors), no display needed
  gui.py           thin tkinter wrapper: drawing and event handling only
  bridge.py        web actions (JSON) -> GameSession -> plain board description (R11.2)
web/
  index.html, style.css, app.js   the page: draws the board, sends taps and buttons; no game logic
  worker.js        web worker: loads Pyodide, Pillow, and meowdoku.zip, answers through bridge.py
  timings.py       prototype measurements for R11.12 (shipped in meowdoku.zip)
  assemble.py      builds the site (page files, meowdoku.zip, sample.png); --serve under /meowdoku/
.github/workflows/pages.yml   tests, assembles, and publishes the site to GitHub Pages
```

Allowed imports (everything may import `puzzle`):

- `cli` -> `image_import`, `parser`, `solver`
- `gui` -> `game`, `state` (never the solver, rules, hints, or deduction directly)
- `bridge` -> `game`, `state` (same limits as `gui`); `web/` calls only `bridge`
- `game` -> `assume`, `colors`, `hints`, `image_import`, `parser`, `solver`, `rules`, `state`
- `hints` -> `assume`, `deduce`, `rules`, `solver`, `state`
- `assume` -> `deduce`, `state`
- `image_import` -> `parser`, `state`
- `deduce`, `rules` -> `state`

- `rules.py` and `solver.py` must never import each other. The validator is an
  independent check on the solver.
- `deduce.py` and `assume.py` must never import `solver.py`. Hints are
  checked against solver output, so they can't depend on it.
- `gui.py` holds no game logic (R8.7).
- An invalid `Puzzle` must be impossible to construct: validate in `__post_init__`.
- A well-formed puzzle with no solution is **not** an error. Report it as
  `SolveStatus.NONE`.
- Never assume a puzzle has a unique solution.

## Code style

- Type hints on every function signature.
- Small functions that can be tested independently. Prefer readability over cleverness.
- Frozen dataclasses for value types. Cells are `(row, col)` tuples, 0-indexed
  internally and 1-indexed in user-facing output.
- User-facing errors raise a `MeowdokuError` subclass with a clear message,
  including line numbers for parse errors. Structural validation collects all
  problems before raising.
- Keep output deterministic. Solutions are produced in a stable order.

## Testing

- Add or update tests with every change. Reference requirement IDs (e.g.
  `R2.3`) in test names or docstrings where useful.
- Do not test the solver only against itself. Use the oracles in
  docs/algorithm.md: rule validator, brute-force enumeration, OEIS A002464
  counts, and metamorphic transforms.
- Random tests must use fixed seeds.

## Git

- Commit after each milestone or coherent step, with all tests passing.
- Use the currently checked-out branch unless the owner says otherwise.
