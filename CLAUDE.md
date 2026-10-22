# CLAUDE.md

Guidance for AI assistants working in this repository.

## Project

Meowdoku Solver: a Python solver for Meowdoku puzzles (see README.md for the
rules). The owner reviews architecture and algorithm decisions before
implementation. **Do not implement features outside docs/requirements.md
without the owner's approval**, and work one approved milestone at a time.

## Stack constraints

- Python 3.11+, standard library only for code under `src/`.
- pytest is the only development dependency. Do not add packages (including
  Hypothesis) without written justification and owner approval.

## Commands

```bash
source .venv/bin/activate
python -m pytest          # run all tests; must pass before every commit
```

## Architecture

```text
src/meowdoku/
  puzzle.py   Puzzle type, structural validation, error types
  parser.py   text -> Puzzle, Solution -> text
  rules.py    solution validator (find_violations)
  solver.py   backtracking search (iter_solutions, solve)
  cli.py      thin command-line wrapper
```

Dependency direction: `cli -> parser, solver, rules -> puzzle`.

- `rules.py` and `solver.py` must never import each other. The validator is an
  independent check on the solver.
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
