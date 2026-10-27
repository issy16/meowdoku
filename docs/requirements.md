# Requirements

Requirement IDs are stable. Tests should reference them where useful.
Changes to this document require owner approval.

## R1 Puzzle rules

A solution to an N×N puzzle is a set of cat positions such that:

- **R1.1** Every row contains exactly one cat.
- **R1.2** Every column contains exactly one cat.
- **R1.3** Every region contains exactly one cat.
- **R1.4** No two cats are adjacent horizontally, vertically, or diagonally.

## R2 Solve results

- **R2.1** The solver reports one of three statuses: `NONE` (zero
  solutions), `UNIQUE` (exactly one), or `MULTIPLE` (two or more).
- **R2.2** The solver must not assume a unique solution. Telling `UNIQUE`
  apart from `MULTIPLE` requires searching for a second solution.
- **R2.3** By default the solver stops after finding two solutions and
  returns both. Callers can ask for every solution (`max_solutions=None`).
- **R2.4** Solutions are returned in a deterministic order: lexicographic by
  the column of the cat in each row, top to bottom.
- **R2.5** A well-formed puzzle with no solution is a valid result
  (`NONE`), not an error.

## R3 Text grid format

Players don't give text files; screenshots are the only input (removed at
the owner's request). This format is internal: screenshot import produces
it, so the same validation (R4) applies, and tests describe boards with it.

- **R3.1** A puzzle is text with one line per board row.
- **R3.2** Each non-whitespace character in a row is one cell's region label.
  Cells with the same label belong to the same region.
- **R3.3** Blank lines and lines whose first non-whitespace character is `#`
  are ignored. Leading and trailing whitespace on a row is stripped.
- **R3.4** Whitespace inside a row is not allowed.

## R4 Input validation and errors

All user-facing errors subclass `MeowdokuError`.

Format errors (`PuzzleFormatError`). Each message includes the 1-indexed
source line number.

- **R4.1** The input contains no rows.
- **R4.2** A row contains internal whitespace.
- **R4.3** Rows have unequal lengths, or the number of rows differs from the
  row length (the board is not square).

Structural errors (`PuzzleValidationError`). All problems are collected and
reported together in `.problems`.

- **R4.4** Board size N must satisfy 1 ≤ N ≤ 16.
- **R4.5** The number of distinct region labels must equal N.
- **R4.6** Every region must be orthogonally connected.
- **R4.7** A `Puzzle` object that violates R4.4–R4.6 cannot be constructed.

## R5 Solution validator

- **R5.1** Given a puzzle and any collection of cells, the validator returns
  a list of rule violations, and an empty list means the solution is valid.
- **R5.2** Each violation names the rule broken (`ROW`, `COLUMN`, `REGION`,
  `ADJACENT`, or `OUT_OF_BOUNDS`), the cells involved, and a readable message.
- **R5.3** The validator is implemented independently of the solver and does
  not import it.

## R6 Command-line interface

- **R6.1** `meowdoku SCREENSHOT` imports the screenshot (R9), solves, and
  prints the status line followed by each solution grid, with cats shown as
  `*`.
- **R6.2** `--count-all` finds and reports the total number of solutions
  instead of stopping at two.
- **R6.3** Exit code 0 when solving completes, whatever the status. Exit code
  2 for invalid input, with the error message on stderr and no traceback.
- **R6.4** Coordinates shown to users are 1-indexed.
- **R6.5** Before the solve result, it prints the detected text grid and any
  cats and ✕ marks it read, so the user can review them. Only `.png`, `.jpg`,
  and `.jpeg` files are accepted; anything else, including text puzzle files,
  is an input error (R6.3).

## R7 Board state and hints

- **R7.1** A `BoardState` records the player's progress: each cell is empty,
  marked ✕ (no cat), or marked as a cat. It is immutable; changes return a new
  state.
- **R7.2** `next_hint(puzzle, state)` returns the next available hint from
  the current state. It never modifies the state.
- **R7.3** A hint names the deduction rule used, the cells it's based on, the
  conclusion (a cat belongs in a cell, or cells can be marked ✕), and a short
  plain-English reason, e.g. "This region has only 1 cell left." The GUI
  highlights the cells, so the reason refers to them ("here", "this row",
  "these regions") and never gives row or column numbers. (Shortened at the
  owner's request.)
- **R7.4** Deduction rules are tried simplest first, in the fixed order in
  docs/algorithm.md. The first rule that gives new information is returned, so
  the same state always gets the same hint.
- **R7.5** Mistakes take priority. If the state breaks a rule (R1), the hint
  points at the conflicting cells. If no solution matches the state, the hint
  says the board has a mistake and, when the puzzle has a unique solution,
  points at the first wrong mark in row-major order.
- **R7.6** Hints never reveal the solution (the GUI's cat check, R8.9, is
  separate). If no deduction rule applies, the
  hint says "No simple step found; try Solve." If the puzzle itself has no
  solution, the hint says so.
- **R7.7** Deduction rules must be sound: a hint never contradicts the
  puzzle's solution.
- **R7.8** In the GUI, hint messages name regions by color, e.g.
  "the pink region", using the closest of a list of named colors that
  includes the real game's tile colors. Regions whose colors get the same
  name are told apart by shade, never by letter: "the lighter orange region"
  and "the darker orange region", or "the lightest", "the second-lightest",
  … "the darkest" for three or more. The command line keeps letters, since
  it shows the letter grid. (Added at the owner's request; shades replaced
  letters at the owner's request.)
- **R7.9** If no rule from D1–D5 applies, D6 (contradiction by assumption)
  tries each open cell as a cat and as empty, applying D1–D5 after each
  assumption. If one assumption leads to a row, column, or region with no
  room for its cat, or to two cats that break R1, the opposite mark is the
  hint. A branch that ends without a contradiction proves nothing. The hint
  explains the assumption, the steps that followed, and why it fails.
  (Added at the owner's request.)

## R8 Graphical interface

- **R8.1** `python -m meowdoku.gui` opens a window built with tkinter
  (standard library).
- **R8.2** The board looks like the Meowdoku app's: rounded colored tiles
  with white gaps between them, on a white rounded card on a beige page. Each
  region has its own tile color, and regions are told apart by color only (no
  grid lines or region borders). ✕ marks are thick white X's, as in the
  game. Cats are line-drawn lucky cat (maneki-neko) faces: white with dark
  outlines, forehead stripes, and almond eyes. (Changed at the owner's
  request from a grid with thick region borders, and from the game's cat
  faces.)
- **R8.3** Puzzles imported from a screenshot keep their original region
  colors. Text puzzles use a built-in palette of at least 16 distinguishable
  colors, assigned in order of each region's first appearance (row-major).
- **R8.4** Clicking a cell toggles it between empty and ✕, and clears a cat.
  Double-clicking a cell places a cat there, whatever it held. A correct cat
  (one in the first solution, R8.9) is locked: clicking or double-clicking it
  does nothing. (Changed at the owner's request from a click cycle
  empty → ✕ → cat → empty, which could no longer clear a ✕ once cats were
  judged; locking also added at the owner's request.)
- **R8.5** Controls: **Open** (a screenshot), **Hint**
  (highlights the hint's cells and shows its reason; it never places marks by
  itself, but its Apply? link makes the move when clicked, R8.11; pressing
  Hint again hides it), **Step by Step** (R8.12), **Solve** (shows a solution over the
  player's marks without changing them, with no message unless there is no
  solution; it stays while the player keeps clicking, and pressing Solve
  again hides it), and **Reset**. (Hint and Solve toggling, Solve without a
  message, and Step by Step in place of Check, at the owner's request; Hint
  still points out broken rules.)
- **R8.6** The move that completes the board as a valid solution shows a
  pop-up over the board: a clean rounded white card with a soft shadow,
  "Puzzle solved!", "Well done!", and a rounded OK button, with no icon. It
  is drawn in the window rather than as a macOS alert. A click anywhere,
  Return, Escape, or the next action closes it, and that click doesn't change
  the board. Nothing else says "Solved!". (Pop-up, its look, and dropping the
  "Solved!" line at the owner's request.)
- **R8.7** The GUI contains no game logic. Rules, hints, and solving live in
  modules that are testable without a display.
- **R8.8** Errors (invalid puzzle, unreadable screenshot) are shown in a
  dialog, never as a traceback.
- **R8.9** A cat the player places by double-clicking is checked against the
  puzzle's first solution (the one Solve shows). A wrong cat turns into a
  plain ✕ and its cell shakes briefly, with no message. A correct cat stays,
  and every
  empty cell in its row, its column, its color region, and the cells touching
  it gets a ✕. Cats from a screenshot aren't checked, and nothing is checked
  when the puzzle has no solution. (Added at the owner's request.)
- **R8.11** A hint that is a logical step (R7.2, a deduction) ends with an
  "Apply?" link. Clicking it makes the step's move for the player: a cat,
  checked like a double-clicked one (R8.9), or ✕ on the cells the step rules
  out. Then the hint is hidden. Hints about mistakes, broken rules, or no
  simple step have no link. (Added at the owner's request.)
- **R8.12** **Step by Step** works like pressing Hint and Apply? over and
  over. The first press shows step 1 (highlighted, with its reason, numbered
  "Step 1: …") and the button turns into **Next Step**. Each Next Step makes the shown
  step's move (R8.11) and shows the next step. Stepping ends when the puzzle
  is solved (with the pop-up, R8.6) or when no step is left, such as "No
  simple step found; try Solve." or a mistake; the button then reads Step by
  Step again. Clicking a cell or another button also ends it. While stepping,
  the message has no Apply? link. (Added at the owner's request.)
- **R8.13** **Previous** and **Next** undo and redo the player's moves. A
  move is a click, a double-clicked cat with the ✕ marks it fills in, a whole
  drag, an Apply?, a Step by Step step, or Reset; a move that changes no mark
  isn't recorded. A new move after Previous ends what Next can redo. The
  buttons are greyed out when there is nothing to undo or redo. Undoing or
  redoing hides a hint and ends Step by Step; redoing the solving move says
  "Solved!" without the pop-up. Opening a screenshot starts a new history.
  While stepping, the Step by Step button reads **Next Step**. (Added at the
  owner's request.)
- **R8.14** A D6 hint (R7.9) also has a "Show me" link, while stepping too.
  It opens a card over the board that walks through the proof on a copy of
  the board, one step per frame, each with its line of the explanation:
  the cell to look at, the assumed mark, the marks each D1–D5 step adds
  (with the cells it's based on highlighted), the row, column, or region
  that breaks (highlighted red), and the mark that follows. Marks that
  exist only in the assumption are drawn dashed. **Back**, **Next** (reading
  **Done** on the last frame), and **Close** move through it; the arrow keys,
  Return, and Escape do too. It never changes the player's marks, and
  closing it leaves the hint showing. Any other action closes it. (Added at
  the owner's request.)
- **R8.10** Pressing on a cell and dragging across others marks or unmarks
  them, decided by the first cell: from an empty cell, every empty cell
  passed over gets a ✕; from a ✕, every ✕ passed over is cleared, except
  ✕ marks that a correct cat on the board rules out (R8.9). Dragging never
  changes cats, and a drag that begins on a cat does nothing. Cells skipped
  by a fast drag are filled in along a straight line. A press and release on
  one cell is a click (R8.4). (Added at the owner's request.)

## R9 Screenshot import

- **R9.1** `import_screenshot(path)` reads a screenshot of a Meowdoku board
  and returns the text grid (R3), each region's RGB color, and the cats and
  ✕ marks on the board.
- **R9.1a** Screenshots may show a game in progress. Cats and ✕ marks are
  read, and the GUI starts from them instead of an empty board; Reset still
  clears them. A tile whose mark is unclear is left empty rather than
  guessed. (Changed at the owner's request; marks were ignored before. The
  window no longer shows a message after opening a screenshot, also at the
  owner's request.)
- **R9.2** It supports PNG and JPEG through Pillow, a regular dependency
  installed with the project.
- **R9.3** It detects the board's position and size N, samples each cell's
  color, and groups the colors into N regions labeled `A`, `B`, `C`, … in
  order of first appearance (row-major).
- **R9.4** The result goes through normal parsing and validation (R3, R4).
  Detection failures raise `ImageImportError` with a specific message, e.g.
  "found 6 region colors; expected 7".
- **R9.5** Supported screenshot layouts are defined by the sample screenshots
  in `tests/fixtures/screenshots/`, each with a hand-checked expected grid.
- **R9.6** Screenshots of this program's own window (R8) can be imported
  too, whole-window screenshots included (a macOS window screenshot's
  transparent shadow is laid over white). The lucky cat faces are read as
  cats and ✕ marks as ✕. Solve's gray cats aren't the player's marks, so
  they read as empty, as does a ✕ hidden under one. Hint rings, orange or
  red, don't affect reading. The window's palette keeps its colors far enough
  apart to import cleanly. The `gui-*` fixtures come from
  `tests/capture_window_screenshots.py`. (Added at the owner's request.)

## R10 Mac app for sharing

Added at the owner's request, so people without Python can use the program.

- **R10.1** `packaging/build.sh` builds `dist/Meowdoku.app` with PyInstaller,
  a build-only tool, and a zip holding the app and *How to open
  Meowdoku.txt*. The app opens the GUI (R8).
- **R10.2** The app runs on Macs with the chip type of the Mac that built
  it; an Intel build also runs on Apple-chip Macs through Rosetta.
- **R10.3** The app is not signed by a paid Apple developer account, so
  receivers approve it once in System Settings; the included text explains
  how.

## R11 Web app with sign-in

Added at the owner's request, so people can play in a browser and pick up
their game on another device. The desktop app (R8, R10) stays.

- **R11.1** The web app is static files: a page, its scripts, and the
  `meowdoku` package. It runs the package in the browser with Pyodide, so
  there is no game server. It supports the current versions of Chrome,
  Safari, Firefox, and Edge on desktop computers, Safari on iPhone and iPad,
  and Chrome on Android phones and tablets.
- **R11.1a** On a phone the board fills the screen's width, upright, with
  the buttons below it, and nothing scrolls sideways. Touch works like the
  mouse: a tap is a click, a double tap places a cat, and dragging a finger
  across cells marks them (R8.10) instead of scrolling the page. Opening a
  screenshot can pick one from the phone's photos.
- **R11.2** The page talks to Python only through a small bridge. Each call
  is one player action (open, click, place cat, drag, hint, apply, solve,
  reset, previous, next) and returns a plain description of the board: the
  marks, highlighted cells, message, and which buttons are enabled. The page
  holds no game logic (as R8.7).
- **R11.3** Python runs in a web worker, so the page stays responsive while
  it loads, hints, or solves, and shows that it is busy.
- **R11.4** Playing follows R8.2–R8.6, R8.9–R8.11, and R8.13 (the look,
  clicks, double-clicks, drag, Hint with Apply?, Solve, Reset, Previous and
  Next, the cat check, and the solved pop-up). Step by Step (R8.12) and Show
  me (R8.14) come in a later release.
- **R11.5** Opening a screenshot reads it on the player's device, as in R9;
  the image is never uploaded or stored. Files other than PNG or JPEG, files
  over 20 MB, and images wider or taller than 8000 pixels are refused with a
  message.
- **R11.6** Anyone can play without signing in. Signing in, through the
  managed sign-in service the owner chooses, lets the game be saved. The
  page shows who is signed in and has a Sign out button.
- **R11.7** For a signed-in player, the current game is saved after each
  move, and after signing in on any supported browser it is restored. Each
  account has one saved game; opening a new screenshot replaces it.
- **R11.8** A save holds a format version, the puzzle as a text grid (R3),
  each region's color, the cats and ✕ marks, and when it was saved. Undo
  history, hints, and the solution are not saved. Loading a save validates
  it like any puzzle (R4); a save that is invalid or from an unknown version
  is reported and the player starts fresh, without crashing.
- **R11.9** A player can read and change only their own save. The service
  enforces this, not the page, and the page holds no key that can bypass it.
- **R11.10** If saving fails, the page says so and keeps the game; it never
  says a game was saved when it wasn't.
- **R11.11** A signed-in player can delete their account and saved game.
- **R11.12** Load and response times are measured in the first prototype on
  a typical laptop and a typical phone; the owner then sets the targets here.
- **R11.13** The web app is published with GitHub Pages from this
  repository (`issy16/meowdoku`) at `https://issy16.github.io/meowdoku/`.
  The owner's résumé at `https://issy16.github.io/` comes from a separate
  repository, and nothing in this project changes, moves, or deletes it.
  The owner may later link to the game from the résumé; that link is the
  URL above, which stays the same.
- **R11.14** The app works under the `/meowdoku/` path. Every page, script,
  style, Python file, and image it loads uses a path relative to the page,
  never one starting with `/`, so it also works from a local folder.
  External files, such as Pyodide when loaded from a CDN, use full pinned
  URLs. The app is one page with no routes of its own: its state never goes
  in the URL, so reloading or sharing `https://issy16.github.io/meowdoku/`
  always works, and it needs no fallback page for unknown paths. The
  prototype is tested served from a `/meowdoku/` folder, not only from the
  site root.
- **R11.15** The résumé and the app share the `issy16.github.io` origin, so
  the browser gives them the same storage. The app names everything it
  stores with a `meowdoku` prefix and never touches other keys. Where the
  sign-in service redirects back (for example after an email link), it
  returns to `https://issy16.github.io/meowdoku/`, and that address, plus a
  local one for testing, are the only ones allowed in the service's
  settings. NFR5 applies to
  the desktop app.

## Non-functional requirements

- **NFR1** Python 3.11+. Pillow is the one runtime dependency, used only by
  screenshot import (R9). It was an optional extra until screenshots became
  the only input; the owner then made it a regular dependency. Everything
  else uses only the standard library.
- **NFR2** pytest is the only development dependency.
- **NFR3** Type hints throughout. Small functions that can be tested independently.
- **NFR4** Output is deterministic for the same input.
- **NFR5** Puzzles up to N = 12 with a unique solution, as in the real game,
  solve in under one second on a typical laptop. Puzzles with no solution or
  several may take longer (accepted by the owner after Milestone 4; timings
  in docs/algorithm.md).
- **NFR6** The web app (R11) adds, with the owner's approval: a pinned
  Pyodide release, the sign-in service's browser client, plain HTML, CSS,
  and JavaScript with no build step, a browser test tool, and GitHub's own
  Pages actions in a workflow that publishes `web/` and the `meowdoku`
  package (R11.13). Its code lives in `web/`; `src/meowdoku/` keeps NFR1.
  Each is named here when chosen.

## Out of scope (for now)

- Photos of screens, rotated or skewed images
- Timers, and saving progress in the Mac app (the web app saves, R11.8)
- Phone or tablet apps from an app store, Windows apps, and signed or
  notarized Mac apps (phones use the web app, R11)
- Several saved games per account, sharing puzzles, leaderboards, and
  checking completions on a server (the web app trusts the browser)
- Puzzle generation
- Pre-placed cats or marked cells in the input
- Text puzzle files, or any input other than PNG/JPEG screenshots (text
  files were removed at the owner's request)
- Non-square boards or region counts other than N
