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

> **Status:** Milestone 3 (solution validator). The solver is not
> implemented yet. See [Roadmap](#roadmap).

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

## Output (planned)

```text
UNIQUE
AABB*
AC*CB
*CDDB
EED*B
E*EBB
```

`*` marks a cat. The status line is `UNIQUE`, `NONE`, or `MULTIPLE`. By
default, a `MULTIPLE` result shows two example solutions. Coordinates shown to
users are 1-indexed.

## Development

Requires Python 3.11 or newer. The solver itself uses only the standard
library. pytest is the only development dependency.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
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
4. Backtracking solver, cross-checked against independent oracles
5. Command-line interface
6. Board state and next-available hints
7. Colored-board GUI (tkinter)
8. Screenshot import (Pillow, optional)
