"""Check the solver against sources that don't depend on it (docs/algorithm.md).

1. Rule validator: every returned solution must have zero violations.
2. Brute force: every permutation filtered by the validator.
3. OEIS A002464: published solution counts for stripe-shaped boards.
4. Metamorphic: symmetric or relabeled puzzles have matching solutions.
"""

import itertools
import random

import pytest

from meowdoku.puzzle import Puzzle
from meowdoku.rules import is_valid_solution
from meowdoku.solver import SolveStatus, iter_solutions, solve

from helpers import (
    LABELS,
    CellTransform,
    column_stripes,
    flip,
    mirror,
    random_puzzle,
    relabel_puzzle,
    rotate,
    row_stripes,
    transform_puzzle,
    transpose,
)

SEED = 20261022
RANDOM_PUZZLE_COUNT = 200


def random_puzzles(sizes: range, count: int, seed: int = SEED) -> list[Puzzle]:
    rng = random.Random(seed)
    return [random_puzzle(rng, rng.choice(sizes)) for _ in range(count)]


RANDOM_SMALL = random_puzzles(range(4, 7), RANDOM_PUZZLE_COUNT)


def all_solution_cats(puzzle: Puzzle) -> list[frozenset[tuple[int, int]]]:
    return [solution.cats for solution in iter_solutions(puzzle)]


def brute_force_columns(puzzle: Puzzle) -> list[tuple[int, ...]]:
    """All valid solutions, found without the solver: try every permutation."""
    return [
        columns
        for columns in itertools.permutations(range(puzzle.size))
        if is_valid_solution(puzzle, list(enumerate(columns)))
    ]


# 1. Rule validator


@pytest.mark.parametrize(
    "puzzle", RANDOM_SMALL[:50] + [row_stripes(8)], ids=lambda puzzle: f"{puzzle.size}x{puzzle.size}"
)
def test_every_solution_passes_the_validator(puzzle: Puzzle) -> None:
    for solution in iter_solutions(puzzle):
        assert is_valid_solution(puzzle, solution.cats)


# 2. Brute force


def test_random_sample_covers_every_status() -> None:
    """Guard: the random puzzles must exercise NONE, UNIQUE, and MULTIPLE."""
    statuses = {solve(puzzle).status for puzzle in RANDOM_SMALL}
    assert statuses == set(SolveStatus)


@pytest.mark.parametrize("index", range(RANDOM_PUZZLE_COUNT))
def test_solver_matches_brute_force(index: int) -> None:
    puzzle = RANDOM_SMALL[index]
    found = [solution.columns for solution in iter_solutions(puzzle)]
    assert found == brute_force_columns(puzzle)


# 3. OEIS A002464 (Hertzsprung's problem)

A002464 = {1: 1, 2: 0, 3: 0, 4: 2, 5: 14, 6: 90, 7: 646, 8: 5242}


@pytest.mark.parametrize(("size", "expected"), A002464.items())
def test_row_stripes_match_oeis_a002464(size: int, expected: int) -> None:
    assert len(solve(row_stripes(size), max_solutions=None).solutions) == expected


@pytest.mark.parametrize(("size", "expected"), A002464.items())
def test_column_stripes_match_oeis_a002464(size: int, expected: int) -> None:
    assert len(solve(column_stripes(size), max_solutions=None).solutions) == expected


# 4. Metamorphic transforms

RANDOM_MEDIUM = random_puzzles(range(5, 9), 40, seed=SEED + 1)


@pytest.mark.parametrize("transform", [rotate, mirror, flip, transpose])
@pytest.mark.parametrize("index", range(len(RANDOM_MEDIUM)))
def test_symmetric_puzzle_has_transformed_solutions(
    index: int, transform: CellTransform
) -> None:
    puzzle = RANDOM_MEDIUM[index]
    n = puzzle.size
    expected = {
        frozenset(transform(cat, n) for cat in cats) for cats in all_solution_cats(puzzle)
    }
    transformed = transform_puzzle(puzzle, transform)
    assert set(all_solution_cats(transformed)) == expected


@pytest.mark.parametrize("index", range(len(RANDOM_MEDIUM)))
def test_relabeled_puzzle_has_identical_solutions(index: int) -> None:
    puzzle = RANDOM_MEDIUM[index]
    new_labels = random.Random(index).sample(LABELS, len(puzzle.region_labels))
    relabeled = relabel_puzzle(puzzle, dict(zip(puzzle.region_labels, new_labels)))
    assert list(iter_solutions(relabeled)) == list(iter_solutions(puzzle))
