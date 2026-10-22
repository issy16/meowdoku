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

## Non-functional requirements

- **NFR1** Python 3.11+. The solver uses only the standard library.
- **NFR2** pytest is the only development dependency.
- **NFR3** Type hints throughout. Small functions that can be tested independently.
- **NFR4** Output is deterministic for the same input.
- **NFR5** Puzzles up to N = 12 solve in under one second on a typical laptop.

## Out of scope (for now)

- Step-by-step deduction explanations (planned later)
- Visual or graphical interface (planned later)
- Puzzle generation
- Pre-placed cats or marked cells in the input
- Input formats other than the text grid (e.g. JSON)
- Non-square boards or region counts other than N
