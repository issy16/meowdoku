"""Screenshot import (R9) on synthetic screenshots, plus real ones when present."""

import itertools
import random
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from meowdoku.game import PALETTE
from meowdoku.gui import HIGHLIGHT_COLORS
from meowdoku.image_import import (
    COLOR_TOLERANCE,
    HIGHLIGHT_RING_COLORS,
    ImageImportError,
    ImportedPuzzle,
    import_screenshot,
    is_image_path,
)
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import MeowdokuError, Puzzle

from helpers import LABELS, random_puzzle
from screenshot_factory import TEST_COLORS, add_phone_ui, draw_screenshot, hex_to_rgb, save

REAL_SCREENSHOTS = Path(__file__).parent / "fixtures" / "screenshots"
EXAMPLE = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])


def canonical(puzzle: Puzzle) -> Puzzle:
    """Relabel regions A, B, C… in order of first appearance, as import does (R9.3)."""
    mapping = {label: LABELS[i] for i, label in enumerate(puzzle.region_labels)}
    return Puzzle.from_rows(["".join(mapping[label] for label in row) for row in puzzle.regions])


def color_distance(a: str, b: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(hex_to_rgb(a), hex_to_rgb(b))) ** 0.5


def test_test_colors_are_far_enough_apart() -> None:
    """Guard for the synthetic tests: colors of different regions must not merge."""
    closest = min(color_distance(a, b) for a, b in itertools.combinations(TEST_COLORS, 2))
    assert closest > 2 * COLOR_TOLERANCE


# R9.1, R9.3 Detection on clean screenshots


def test_r9_1_reads_example_board_and_colors(tmp_path: Path) -> None:
    path = save(draw_screenshot(EXAMPLE), tmp_path / "example.png")
    imported = import_screenshot(path)
    assert imported.puzzle == EXAMPLE
    assert imported.text == "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"
    for i, label in enumerate("ABCDE"):
        assert color_distance(imported.colors[label], TEST_COLORS[i]) <= 3


RNG = random.Random(20261024)
VARIATIONS = [
    (random_puzzle(RNG, size), cell, origin)
    for size, cell, origin in [
        (4, 114, (60, 40)),
        (5, 90, (30, 70)),
        (6, 72, (48, 24)),
        (7, 64, (20, 60)),
        (8, 56, (40, 30)),
        (9, 48, (36, 50)),
        (10, 114, (37, 53)),  # the real screenshot's scale
        (11, 40, (30, 40)),
        (12, 34, (40, 36)),
    ]
]
IDS = [f"{puzzle.size}x{puzzle.size}" for puzzle, _, _ in VARIATIONS]


@pytest.mark.parametrize(("puzzle", "cell", "origin"), VARIATIONS, ids=IDS)
def test_r9_3_reads_boards_of_many_sizes(
    tmp_path: Path, puzzle: Puzzle, cell: int, origin: tuple[int, int]
) -> None:
    image = draw_screenshot(puzzle, cell=cell, origin=origin)
    assert import_screenshot(save(image, tmp_path / "board.png")).puzzle == canonical(puzzle)


@pytest.mark.parametrize(("puzzle", "cell", "origin"), VARIATIONS, ids=IDS)
def test_r9_2_reads_jpeg_screenshots(
    tmp_path: Path, puzzle: Puzzle, cell: int, origin: tuple[int, int]
) -> None:
    image = draw_screenshot(puzzle, cell=cell, origin=origin)
    assert import_screenshot(save(image, tmp_path / "board.jpg", quality=80)).puzzle == canonical(puzzle)


# R9.1a Marks are read


def random_marks(puzzle: Puzzle, seed: int) -> dict[tuple[int, int], str]:
    rng = random.Random(seed)
    return {cell: rng.choice(["cat", "cross"]) for cell in puzzle.cells() if rng.random() < 0.5}


def assert_marks(imported: "ImportedPuzzle", marks: dict[tuple[int, int], str]) -> None:
    assert imported.cats == {cell for cell, mark in marks.items() if mark == "cat"}
    assert imported.crosses == {cell for cell, mark in marks.items() if mark == "cross"}


@pytest.mark.parametrize("index", range(len(VARIATIONS)), ids=IDS)
def test_r9_1a_cats_and_crosses_are_read(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    marks = random_marks(puzzle, index)
    image = draw_screenshot(puzzle, cell=cell, origin=origin, marks=marks)
    imported = import_screenshot(save(image, tmp_path / "board.png"))
    assert imported.puzzle == canonical(puzzle)
    assert_marks(imported, marks)


@pytest.mark.parametrize("index", range(0, len(VARIATIONS), 2), ids=IDS[::2])
def test_r9_1a_marks_are_read_from_jpeg(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    marks = random_marks(puzzle, index)
    image = draw_screenshot(puzzle, cell=cell, origin=origin, marks=marks)
    imported = import_screenshot(save(image, tmp_path / "board.jpg", quality=80))
    assert imported.puzzle == canonical(puzzle)
    assert_marks(imported, marks)


def test_r9_1a_empty_board_has_no_marks(tmp_path: Path) -> None:
    imported = import_screenshot(save(draw_screenshot(EXAMPLE), tmp_path / "example.png"))
    assert imported.cats == frozenset()
    assert imported.crosses == frozenset()


def test_marks_text() -> None:
    imported = ImportedPuzzle(EXAMPLE, "", {}, frozenset({(0, 0)}), frozenset({(0, 1), (4, 4)}))
    assert imported.marks_text == "*x...\n.....\n.....\n.....\n....x"


# R9.2, R9.4 Errors


def test_r9_4_no_board_in_image(tmp_path: Path) -> None:
    path = save(Image.new("RGB", (400, 700), "white"), tmp_path / "blank.png")
    with pytest.raises(ImageImportError, match="couldn't find the board: no colored tiles"):
        import_screenshot(path)


def test_r9_4_no_square_grid_of_tiles(tmp_path: Path) -> None:
    """A wide colored banner alone is not a board."""
    image = Image.new("RGB", (400, 700), "#f6f2ef")
    ImageDraw.Draw(image).rectangle((20, 300, 380, 400), fill="#3b82f6")
    with pytest.raises(ImageImportError, match="no square grid of colored tiles"):
        import_screenshot(save(image, tmp_path / "banner.png"))


# Full, uncropped phone screenshots


@pytest.mark.parametrize("index", range(len(VARIATIONS)), ids=IDS)
def test_reads_full_phone_screenshots(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    image = add_phone_ui(draw_screenshot(puzzle, cell=cell, origin=origin), seed=index)
    assert import_screenshot(save(image, tmp_path / "phone.png")).puzzle == canonical(puzzle)


@pytest.mark.parametrize("size", range(2, 7))
def test_reads_small_boards_with_big_tiles_on_a_phone(tmp_path: Path, size: int) -> None:
    """The gaps between big tiles are wide, so bridging can't use a fixed pixel width."""
    puzzle = random_puzzle(random.Random(size), size)
    image = add_phone_ui(draw_screenshot(puzzle, cell=1130 // size, origin=(38, 40)), seed=size)
    assert import_screenshot(save(image, tmp_path / "phone.png")).puzzle == canonical(puzzle)


@pytest.mark.parametrize("index", range(0, len(VARIATIONS), 2), ids=IDS[::2])
def test_reads_full_phone_screenshots_with_marks_as_jpeg(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    rng = random.Random(index)
    marks = {cell_: rng.choice(["cat", "cross"]) for cell_ in puzzle.cells() if rng.random() < 0.5}
    image = add_phone_ui(draw_screenshot(puzzle, cell=cell, origin=origin, marks=marks), seed=index)
    imported = import_screenshot(save(image, tmp_path / "phone.jpg", quality=80))
    assert imported.puzzle == canonical(puzzle)
    assert_marks(imported, marks)


def test_r9_4_two_regions_with_the_same_color(tmp_path: Path) -> None:
    """Region D is repainted in region A's color, so only 4 colors remain."""
    image = draw_screenshot(EXAMPLE)
    pixels = image.load()
    a_color = hex_to_rgb(TEST_COLORS[0])
    d_color = hex_to_rgb(TEST_COLORS[3])
    for x in range(image.width):
        for y in range(image.height):
            if pixels[x, y] == d_color:
                pixels[x, y] = a_color
    with pytest.raises(ImageImportError, match="found 4 region colors; expected 5"):
        import_screenshot(save(image, tmp_path / "board.png"))


def test_r9_4_detected_grid_still_goes_through_validation(tmp_path: Path) -> None:
    """Two separate regions with the same color form one split region (R4.6)."""
    rows = ["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"]
    image = draw_screenshot(Puzzle.from_rows(rows))
    pixels = image.load()
    c_color, e_color = hex_to_rgb(TEST_COLORS[2]), hex_to_rgb(TEST_COLORS[4])
    for x in range(image.width):
        for y in range(image.height):
            if pixels[x, y] == c_color:
                pixels[x, y] = e_color
    with pytest.raises(MeowdokuError):
        import_screenshot(save(image, tmp_path / "board.png"))


def test_r9_4_not_an_image(tmp_path: Path) -> None:
    path = tmp_path / "fake.png"
    path.write_text("not an image", encoding="utf-8")
    with pytest.raises(ImageImportError, match="not a readable PNG or JPEG image"):
        import_screenshot(path)


def test_missing_file_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        import_screenshot(tmp_path / "missing.png")


def test_text_files_are_not_screenshots(tmp_path: Path) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("AB\nAB", encoding="utf-8")
    with pytest.raises(ImageImportError, match="puzzle.txt is not a screenshot"):
        import_screenshot(path)


def test_is_image_path() -> None:
    assert is_image_path(Path("a.PNG"))
    assert is_image_path(Path("b.jpeg"))
    assert not is_image_path(Path("c.txt"))


# R9.6 Screenshots of this program's window. The gui-* fixtures come from
# tests/capture_window_screenshots.py and are checked by test_r9_5_real_screenshots.


def test_r9_6_window_palette_colors_stay_apart() -> None:
    """Every two window colors are farther apart than import merges, with room to spare."""
    closest = min(color_distance(a, b) for a, b in itertools.combinations(PALETTE, 2))
    assert closest > 2 * COLOR_TOLERANCE


def test_r9_6_ring_colors_match_the_window() -> None:
    assert {hex_to_rgb(color) for color in HIGHLIGHT_COLORS.values()} == set(HIGHLIGHT_RING_COLORS)


def test_r9_6_no_tile_color_is_mistaken_for_a_ring() -> None:
    """Rings are left out of the tile mask, so no tile may come within its contrast of a ring."""
    for color in PALETTE:
        for ring in HIGHLIGHT_RING_COLORS:
            assert max(abs(a - b) for a, b in zip(hex_to_rgb(color), ring)) > 40, color


def test_r9_6_transparent_window_shadow_is_laid_over_white(tmp_path: Path) -> None:
    """A macOS window screenshot: the board inside a transparent margin with a soft shadow."""
    board = draw_screenshot(EXAMPLE).convert("RGBA")
    image = Image.new("RGBA", (board.width + 120, board.height + 120), (0, 0, 0, 0))
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 90))
    image.alpha_composite(shadow, (70, 75))
    image.alpha_composite(board, (60, 60))
    imported = import_screenshot(save(image, tmp_path / "window.png"))
    assert imported.puzzle == EXAMPLE


# R9.5 Real screenshots: each image needs a .txt file beside it with the expected
# grid, and a .marks file if it shows cats or crosses (* cat, x cross, . empty).


def real_screenshot_cases() -> list[Path]:
    if not REAL_SCREENSHOTS.is_dir():
        return []
    return sorted(path for path in REAL_SCREENSHOTS.iterdir() if is_image_path(path))


@pytest.mark.parametrize("path", real_screenshot_cases(), ids=lambda path: path.name)
def test_r9_5_real_screenshots(path: Path) -> None:
    expected = parse_puzzle(path.with_suffix(".txt").read_text(encoding="utf-8"))
    imported = import_screenshot(path)
    assert imported.puzzle == canonical(expected)
    assert imported.marks_text == expected_marks(path, expected.size)


def expected_marks(path: Path, size: int) -> str:
    marks_path = path.with_suffix(".marks")
    if not marks_path.exists():
        return "\n".join("." * size for _ in range(size))
    lines = marks_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line.strip() for line in lines if line.strip() and not line.startswith("#"))


# Using screenshots from the CLI (R6.5) and the GUI (R8.3, R8.5)


def test_r6_5_cli_prints_detected_grid_then_solves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from meowdoku.cli import EXIT_OK, main

    path = save(draw_screenshot(EXAMPLE), tmp_path / "example.png")
    assert main([str(path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("Detected puzzle:\nAABBB\nACCCB\nACDDB\nEEDDB\nEEEBB\n\nUNIQUE\n")


def test_r6_5_cli_reports_unreadable_screenshot(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meowdoku.cli import EXIT_INPUT_ERROR, main

    path = save(Image.new("RGB", (300, 500), "white"), tmp_path / "blank.png")
    assert main([str(path)]) == EXIT_INPUT_ERROR
    assert "couldn't find the board" in capsys.readouterr().err


def test_r8_3_game_opened_from_screenshot_keeps_its_colors(tmp_path: Path) -> None:
    from meowdoku.game import IMPORTED_MESSAGE, GameSession

    session = GameSession.from_screenshot(save(draw_screenshot(EXAMPLE), tmp_path / "example.png"))
    assert session.puzzle == EXAMPLE
    assert color_distance(session.colors["A"], TEST_COLORS[0]) <= 3
    assert session.message == IMPORTED_MESSAGE


def test_r9_1a_game_starts_from_imported_marks(tmp_path: Path) -> None:
    from meowdoku.game import GameSession

    marks = {(0, 4): "cat", (1, 0): "cross", (2, 2): "cross"}
    session = GameSession.from_screenshot(save(draw_screenshot(EXAMPLE, marks=marks), tmp_path / "b.png"))
    assert session.state.cats == {(0, 4)}
    assert session.state.crosses == {(1, 0), (2, 2)}
    assert session.message == (
        "Read from the screenshot, with 1 cat and 2 ✕ marks. Check that the board matches your game."
    )
    session.reset()
    assert session.state.cats == frozenset()


def test_r6_5_cli_prints_detected_marks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meowdoku.cli import main

    marks = {(0, 4): "cat", (1, 0): "cross"}
    main([str(save(draw_screenshot(EXAMPLE, marks=marks), tmp_path / "b.png"))])
    out = capsys.readouterr().out
    assert "Detected marks (* cat, x cross):\n....*\nx....\n.....\n.....\n.....\n" in out
