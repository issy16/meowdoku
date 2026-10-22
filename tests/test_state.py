from dataclasses import FrozenInstanceError

import pytest

from meowdoku.state import BoardState, Mark


def test_r7_1_empty_board_has_only_open_cells() -> None:
    state = BoardState.empty(3)
    assert state.cats == frozenset()
    assert state.crosses == frozenset()
    assert state.is_open((1, 1))
    assert state.mark_at((1, 1)) is None


def test_r7_1_with_mark_returns_new_state() -> None:
    empty = BoardState.empty(3)
    marked = empty.with_mark((0, 1), Mark.CAT)
    assert marked.mark_at((0, 1)) is Mark.CAT
    assert not marked.is_open((0, 1))
    assert empty.is_open((0, 1))


def test_with_mark_replaces_and_clears() -> None:
    state = BoardState.empty(3).with_mark((0, 1), Mark.CAT).with_mark((0, 1), Mark.CROSS)
    assert state.cats == frozenset()
    assert state.crosses == {(0, 1)}
    assert state.with_mark((0, 1), None) == BoardState.empty(3)


def test_with_crosses_marks_every_cell() -> None:
    state = BoardState.empty(3).with_mark((0, 0), Mark.CAT).with_crosses([(0, 0), (2, 2)])
    assert state.crosses == {(0, 0), (2, 2)}
    assert state.cats == frozenset()


def test_state_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        BoardState.empty(3).size = 4  # type: ignore[misc]


def test_cells_outside_board_are_rejected() -> None:
    with pytest.raises(ValueError, match="outside"):
        BoardState(3, cats=frozenset({(3, 0)}))


def test_cell_cannot_be_both_cat_and_cross() -> None:
    with pytest.raises(ValueError, match="both"):
        BoardState(3, cats=frozenset({(1, 1)}), crosses=frozenset({(1, 1)}))
