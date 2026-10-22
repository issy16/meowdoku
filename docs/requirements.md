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

## R3 Input format

- **R3.1** A puzzle is UTF-8 text with one line per board row.
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

- **R6.1** `meowdoku PUZZLE_FILE` parses, solves, and prints the status line
  followed by each solution grid, with cats shown as `*`.
- **R6.2** `--count-all` finds and reports the total number of solutions
  instead of stopping at two.
- **R6.3** Exit code 0 when solving completes, whatever the status. Exit code
  2 for invalid input, with the error message on stderr and no traceback.
- **R6.4** Coordinates shown to users are 1-indexed.
- **R6.5** The CLI also accepts a `.png` or `.jpg` screenshot (R9). It prints
  the detected text grid before the solve result so the user can review it.

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
- **R7.6** Hints never reveal the solution. If no deduction rule applies, the
  hint says "No simple step found; try Solve." If the puzzle itself has no
  solution, the hint says so.
- **R7.7** Deduction rules must be sound: a hint never contradicts the
  puzzle's solution.

## R8 Graphical interface

- **R8.1** `python -m meowdoku.gui` opens a window built with tkinter
  (standard library).
- **R8.2** The board is a simple colored grid in the style of the Meowdoku
  app: each region has its own fill color, with thick borders between regions
  and thin lines inside them.
- **R8.3** Puzzles imported from a screenshot keep their original region
  colors. Text puzzles use a built-in palette of at least 16 distinguishable
  colors, assigned in order of each region's first appearance (row-major).
- **R8.4** Clicking a cell cycles it: empty → ✕ → cat → empty.
- **R8.5** Controls: **Open** (a text puzzle or a screenshot), **Hint**
  (highlights the hint's cells and shows its reason; it never places marks,
  so the player makes the move), **Check** (highlights rule violations), **Solve** (shows a solution,
  noting when there are several or none), and **Reset**.
- **R8.6** When the board is a complete valid solution, the window shows
  "Solved!".
- **R8.7** The GUI contains no game logic. Rules, hints, and solving live in
  modules that are testable without a display.
- **R8.8** Errors (invalid puzzle, unreadable screenshot, Pillow missing) are
  shown in a dialog, never as a traceback.

## R9 Screenshot import

- **R9.1** `import_screenshot(path)` reads a screenshot of a Meowdoku board
  and returns the text grid (R3) plus each region's RGB color.
- **R9.1a** Screenshots may show a game in progress. Any cats or ✕ marks are
  ignored, and the puzzle is imported as an empty board.
- **R9.2** It supports PNG and JPEG through Pillow, installed as the optional
  `[image]` extra. Every other feature works without Pillow. If Pillow is
  missing, import raises a `MeowdokuError` that includes the install command.
- **R9.3** It detects the board's position and size N, samples each cell's
  color, and groups the colors into N regions labeled `A`, `B`, `C`, … in
  order of first appearance (row-major).
- **R9.4** The result goes through normal parsing and validation (R3, R4).
  Detection failures raise `ImageImportError` with a specific message, e.g.
  "found 6 region colors; expected 7".
- **R9.5** Supported screenshot layouts are defined by the sample screenshots
  in `tests/fixtures/screenshots/`, each with a hand-checked expected grid.

## Non-functional requirements

- **NFR1** Python 3.11+. Everything uses only the standard library, except
  that screenshot import (R9) uses Pillow as an optional extra.
- **NFR2** pytest is the only development dependency.
- **NFR3** Type hints throughout. Small functions that can be tested independently.
- **NFR4** Output is deterministic for the same input.
- **NFR5** Puzzles up to N = 12 solve in under one second on a typical laptop.

## Out of scope (for now)

- Importing the player's cats or ✕ marks from screenshots (they are ignored)
- Photos of screens, rotated or skewed images
- Undo/redo, timers, and saving progress
- Web or mobile interfaces
- Puzzle generation
- Pre-placed cats or marked cells in the input
- Input formats other than the text grid (e.g. JSON)
- Non-square boards or region counts other than N
