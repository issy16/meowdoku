# Meowdoku Solver

A Python program that solves Meowdoku puzzles using constraint satisfaction
and backtracking search. It reports whether a puzzle has **no solution**,
**exactly one solution**, or **multiple solutions**.

Planned features:

- **Screenshot import:** load a screenshot of a Meowdoku board. Any cats or
  ✕ marks in it are ignored, so you start from an empty board.
- **Colored board UI:** play on a simple colored grid like the Meowdoku app.
- **Next available hint:** get the next logical step from your current
  progress, with a plain-English reason. Hints never reveal answers or
  place marks for you.

> **Status:** All 8 milestones are built. Screenshot import is tuned on
> synthetic images and still needs checking against real Meowdoku
> screenshots. See [Roadmap](#roadmap).

## Rules

A Meowdoku puzzle is an N×N board divided into N colored regions. Place cats so that:

1. Every row contains exactly one cat.
2. Every column contains exactly one cat.
3. Every region contains exactly one cat.
4. No two cats touch, not even diagonally.

## Input format

A puzzle is a plain-text file with one line per row and one character per
cell. Each character is a region label, and cells with the same label belong
to the same region. Blank lines and lines starting with `#` are ignored.

```text
# 5x5 example with a unique solution
AABBB
ACCCB
ACDDB
EEDDB
EEEBB
```

Requirements: the grid must be square, with N distinct region labels for
an N×N board, every region orthogonally connected, and 1 ≤ N ≤ 16. See
[docs/requirements.md](docs/requirements.md) for the full specification.

## Usage

```bash
meowdoku tests/fixtures/example_5x5.txt
```

```text
UNIQUE

AABB*
AC*CB
*CDDB
EED*B
E*EBB
5 cats: row 1, column 5; row 2, column 3; row 3, column 1; row 4, column 4; row 5, column 2
```

- `*` marks a cat. Rows and columns are numbered from 1.
- The first line is the status: `UNIQUE`, `NONE`, or `MULTIPLE`. A
  `MULTIPLE` result shows the first two solutions.
- `--count-all` also prints `Solutions: N`, the total number of solutions.
  This can be slow on boards with many solutions.
- Exit code 0 means the puzzle was solved (whatever the status). Exit code 2
  means the input was invalid, with the reason printed to stderr.

`python -m meowdoku PUZZLE_FILE` does the same thing.

### From a screenshot

```bash
meowdoku my-screenshot.png
```

PNG and JPEG screenshots of a Meowdoku board work in place of a text file.
The command prints the grid it detected, so you can check it, then solves.
Cats and ✕ marks in the screenshot are ignored. This needs Pillow:
`python -m pip install -e ".[image]"`.

## Playing in a window

```bash
python -m meowdoku.gui tests/fixtures/example_5x5.txt
```

Without a file, the window opens the example puzzle. **Open…** loads a puzzle
file or a screenshot. Screenshots keep the game's own region colors.

- Click a cell to cycle it: empty → ✕ → cat → empty.
- **Hint** highlights the cells behind the next logical step (orange) and
  explains it below the board. It never places marks for you. Wrong marks and
  broken rules are outlined in red instead.
- **Check** outlines cats that break a rule in red.
- **Solve** shows a solution in gray without changing your marks.
- **Reset** clears the board. "Solved!" appears when you finish.

## Development

Requires Python 3.11 or newer. The solver itself uses only the standard
library. pytest is the only development dependency.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,image]"
python -m pytest
```

## Project layout

```text
src/meowdoku/      package source
tests/             pytest test suite
docs/              requirements and algorithm design
```

## Roadmap

1. Scaffolding and documentation ✅
2. Puzzle representation, parser, and input validation ✅
3. Solution validator (rule checker) ✅
4. Backtracking solver, cross-checked against independent oracles ✅
5. Command-line interface ✅
6. Board state and next-available hints ✅
7. Colored-board GUI (tkinter) ✅
8. Screenshot import (Pillow, optional) ✅ (real-screenshot tuning pending)
