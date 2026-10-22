# CLAUDE.md

Guidance for AI assistants working in this repository.

## Project

Meowdoku Solver: a Python solver for Meowdoku puzzles (see README.md for the
rules). The owner reviews architecture and algorithm decisions before
implementation. **Do not implement features outside docs/requirements.md
without the owner's approval**, and work one approved milestone at a time.

## Stack constraints

- Python 3.11+, standard library only for code under `src/`. The one
  approved exception: Pillow, as the optional `[image]` extra, imported only
  inside `image_import.py` and only when that function is called.
- The GUI uses tkinter (standard library).
- pytest is the only development dependency. Do not add packages (including
  Hypothesis) without written justification and owner approval.

## Commands

```bash
source .venv/bin/activate
python -m pytest          # run all tests; must pass before every commit
```

Screenshot tests need the image extra (`pip install -e ".[dev,image]"`);
without Pillow they are skipped, and everything else must still pass.

## Architecture

```text
src/meowdoku/
  puzzle.py        Puzzle type, structural validation, error types
  parser.py        text/file -> Puzzle, Puzzle + cats -> text
  rules.py         solution validator (find_violations)
  solver.py        backtracking search (iter_solutions, solve)
  state.py         BoardState: player's cats and ✕ marks
  deduce.py        deduction rules D1–D5 (see docs/algorithm.md)
  hints.py         next_hint: violations, mistakes, deductions (never reveals answers)
  image_import.py  screenshot -> text grid + region colors (Pillow)
  colors.py        plain color names for regions ("the pink region")
  cli.py           thin command-line wrapper
  game.py          GameSession: GUI behavior (clicks, buttons, colors), no display needed
  gui.py           thin tkinter wrapper: drawing and event handling only
```

Allowed imports (everything may import `puzzle`):

- `cli` -> `image_import`, `parser`, `solver`
- `gui` -> `game`, `state` (never the solver, rules, hints, or deduction directly)
- `game` -> `colors`, `hints`, `image_import`, `parser`, `solver`, `rules`, `state`
- `hints` -> `deduce`, `rules`, `solver`, `state`
- `image_import` -> `parser`
- `deduce`, `rules` -> `state`

- `rules.py` and `solver.py` must never import each other. The validator is an
  independent check on the solver.
- `deduce.py` must never import `solver.py`. Hints are checked against
  solver output, so they can't depend on it.
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
