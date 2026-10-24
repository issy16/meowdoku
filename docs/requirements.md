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
  conclusion (a cat belongs in a cell, or cells can be marked ✕), and a plain-English
  reason using 1-indexed row and column numbers.
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
- **R7.8** In the GUI, hint and Check messages name regions by color, e.g.
  "the pink region", using the closest of a list of named colors that
  includes the real game's tile colors. If two regions would get the same
  name, both keep their letter: "region 'A' (green)". The command line keeps
  letters, since it shows the letter grid. (Added at the owner's request.)

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
- **R8.4** Clicking a cell cycles it: empty → ✕ → cat → empty.
- **R8.5** Controls: **Open** (a screenshot), **Hint**
  (highlights the hint's cells and shows its reason; it never places marks,
  so the player makes the move; pressing Hint again hides it), **Check**
  (highlights rule violations), **Solve** (shows a solution over the
  player's marks without changing them, noting when there are several or
  none; it stays while the player keeps clicking, and pressing Solve again
  hides it), and **Reset**. (Hint and Solve toggling added at the owner's
  request.)
- **R8.6** When the board is a complete valid solution, the window shows
  "Solved!".
- **R8.7** The GUI contains no game logic. Rules, hints, and solving live in
  modules that are testable without a display.
- **R8.8** Errors (invalid puzzle, unreadable screenshot) are shown in a
  dialog, never as a traceback.
- **R8.9** A cat the player places by clicking is checked against the
  puzzle's first solution (the one Solve shows). A wrong cat turns into a
  plain ✕, with a message saying so. A correct cat stays, and every
  empty cell in its row, its column, its color region, and the cells touching
  it gets a ✕. Cats from a screenshot aren't checked, and nothing is checked
  when the puzzle has no solution. (Added at the owner's request.)

## R9 Screenshot import

- **R9.1** `import_screenshot(path)` reads a screenshot of a Meowdoku board
  and returns the text grid (R3), each region's RGB color, and the cats and
  ✕ marks on the board.
- **R9.1a** Screenshots may show a game in progress. Cats and ✕ marks are
  read, and the GUI starts from them instead of an empty board; Reset still
  clears them. A tile whose mark is unclear is left empty rather than
  guessed. The GUI says how many cats and ✕ marks it read, so the player can
  check them. (Changed at the owner's request; marks were ignored before.)
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
  they read as empty, as does a ✕ hidden under one. Hint and Check rings
  don't affect reading. The window's palette keeps its colors far enough
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

## Out of scope (for now)

- Photos of screens, rotated or skewed images
- Undo/redo, timers, and saving progress
- Web or mobile interfaces, Windows apps, and signed or notarized Mac apps
- Puzzle generation
- Pre-placed cats or marked cells in the input
- Text puzzle files, or any input other than PNG/JPEG screenshots (text
  files were removed at the owner's request)
- Non-square boards or region counts other than N
