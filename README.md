# Meowdoku Solver

A Python program that solves Meowdoku puzzles using constraint satisfaction
and backtracking search. It reports whether a puzzle has **no solution**,
**exactly one solution**, or **multiple solutions**.

Planned features:

- **Screenshot import:** load a screenshot of a Meowdoku board, empty or in
  progress. Cats and ✕ marks are read too, so you continue where you left off.
- **Colored board UI:** play on a simple colored grid like the Meowdoku app.
- **Next available hint:** get the next logical step from your current
  progress, with a plain-English reason. Hints never reveal answers or
  place marks for you.

> **Status:** All 8 milestones are built. Screenshot import reads both real
> screenshots so far (empty 10×10 boards, one cropped and one full-screen).
> Boards with cats and ✕ marks haven't been tried on real screenshots yet.
> See [Roadmap](#roadmap).

## Rules

A Meowdoku puzzle is an N×N board divided into N colored regions. Place cats so that:

1. Every row contains exactly one cat.
2. Every column contains exactly one cat.
3. Every region contains exactly one cat.
4. No two cats touch, not even diagonally.

## Usage

Give the `meowdoku` command a screenshot of the game, either a full phone
screenshot or one cropped to the board (PNG or JPEG):

```bash
meowdoku tests/fixtures/screenshots/IMG_7128.jpg
```

```text
Detected puzzle:
ABBBBBBBCC
ABDDEECCCC
AAADEECFCA
AGADEEEFFA
AGADDDEFFA
AGAAHHFFFA
AGIAAHFFAA
AIIIAHFFFA
AIJJAHFFAA
AJJJAAAAAA

UNIQUE

ABBBBBB*CC
ABDDEECCC*
*AADEECFCA
AGADEE*FFA
AGAD*DEFFA
AGAAHHFF*A
A*IAAHFFAA
AII*AHFFFA
AIJJA*FFAA
AJ*JAAAAAA
10 cats: row 1, column 8; row 2, column 10; row 3, column 1; row 4, column 7; row 5, column 5; row 6, column 9; row 7, column 2; row 8, column 4; row 9, column 6; row 10, column 3
```

- First comes the grid it detected, one letter per region, so you can check
  it against the game. If the screenshot shows cats or ✕ marks, they are
  printed next (`*` cat, `x` ✕).
- Then the status: `UNIQUE`, `NONE`, or `MULTIPLE`, and the solution with
  `*` for cats. A `MULTIPLE` result shows the first two solutions. Rows and
  columns are numbered from 1.
- `--count-all` also prints `Solutions: N`, the total number of solutions.
  This can be slow on boards with many solutions.
- Exit code 0 means the puzzle was solved (whatever the status). Exit code 2
  means the input was invalid, with the reason printed to stderr. Text files
  aren't accepted.

`python -m meowdoku SCREENSHOT` does the same thing.

## Playing in a window

```bash
python -m meowdoku.gui tests/fixtures/screenshots/IMG_7117.PNG
```

Without a screenshot, the window opens a built-in example puzzle. **Open…**
loads a screenshot. The board keeps the game's own region colors and starts
with the cats and ✕ marks from the screenshot.

- Click a cell to cycle it: empty → ✕ → cat → empty.
- When you place a cat, it's checked against the solution. A wrong cat turns
  into a ✕. A correct cat stays and fills in
  ✕ marks for you: its row, its column, its color region, and the cells
  touching it.
- **Hint** highlights the cells behind the next logical step (orange) and
  explains it below the board, naming regions by color ("the pink region"). It never places marks for you. Wrong marks and
  broken rules are outlined in red instead. Press Hint again to hide it.
- **Check** outlines cats that break a rule in red.
- **Solve** shows a solution in gray without changing your marks. It stays
  while you keep playing; press Solve again to hide it.
- **Reset** clears the board. "Solved!" appears when you finish.

## Sharing as a Mac app

Build a double-clickable **Meowdoku.app** that people can use without
installing Python:

```bash
python -m pip install -e ".[build]"
packaging/build.sh
```

This makes `dist/Meowdoku.app` and `dist/Meowdoku-mac-<chip>.zip`. Send the
zip. It unpacks to a folder with the app and *How to open Meowdoku.txt*.

- **Chip type:** the app runs on Macs with the same chip type as the Mac
  that built it. An Intel (`x86_64`) build also runs on Apple-chip Macs
  through Rosetta, which macOS offers to install the first time. Build on
  an Apple-chip Mac for a native `arm64` version.
- **Security warning:** the app isn't signed with a paid Apple developer
  account, so macOS blocks it the first time. The receiver opens it once
  via System Settings > Privacy & Security > **Open Anyway**; the included
  instructions explain this step by step.

## Development

Requires Python 3.11 or newer. Installing the project also installs Pillow,
which reads screenshots; the solver itself uses only the standard library.
pytest is the only development dependency.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Project layout

```text
src/meowdoku/      package source
packaging/         Mac app build script, icon, and instructions for receivers
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
8. Screenshot import (Pillow) ✅ (tuned on three real screenshots)
