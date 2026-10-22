"""Screenshot import (R9) on synthetic screenshots, plus real ones when present."""

import itertools
import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image, ImageDraw  # noqa: E402

from meowdoku.image_import import (  # noqa: E402
    COLOR_TOLERANCE,
    ImageImportError,
    import_screenshot,
    is_image_path,
)
from meowdoku.parser import read_puzzle_file  # noqa: E402
from meowdoku.puzzle import MeowdokuError, Puzzle  # noqa: E402

from helpers import LABELS, random_puzzle  # noqa: E402
from screenshot_factory import TEST_COLORS, add_phone_ui, draw_screenshot, hex_to_rgb, save  # noqa: E402

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


# R9.1a Marks are ignored


@pytest.mark.parametrize("index", range(len(VARIATIONS)), ids=IDS)
def test_r9_1a_cats_and_crosses_are_ignored(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    rng = random.Random(index)
    marks = {cell_: rng.choice(["cat", "cross"]) for cell_ in puzzle.cells() if rng.random() < 0.5}
    image = draw_screenshot(puzzle, cell=cell, origin=origin, marks=marks)
    assert import_screenshot(save(image, tmp_path / "board.png")).puzzle == canonical(puzzle)


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


@pytest.mark.parametrize("index", range(0, len(VARIATIONS), 2), ids=IDS[::2])
def test_reads_full_phone_screenshots_with_marks_as_jpeg(tmp_path: Path, index: int) -> None:
    puzzle, cell, origin = VARIATIONS[index]
    rng = random.Random(index)
    marks = {cell_: rng.choice(["cat", "cross"]) for cell_ in puzzle.cells() if rng.random() < 0.5}
    image = add_phone_ui(draw_screenshot(puzzle, cell=cell, origin=origin, marks=marks), seed=index)
    assert import_screenshot(save(image, tmp_path / "phone.jpg", quality=80)).puzzle == canonical(puzzle)


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


def test_r9_2_missing_pillow_explains_how_to_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "PIL", None)
    with pytest.raises(MeowdokuError, match=r'pip install -e "\.\[image\]"'):
        import_screenshot(tmp_path / "board.png")


def test_is_image_path() -> None:
    assert is_image_path(Path("a.PNG"))
    assert is_image_path(Path("b.jpeg"))
    assert not is_image_path(Path("c.txt"))


# R9.5 Real screenshots: each image needs a .txt file beside it with the expected grid


def real_screenshot_cases() -> list[Path]:
    if not REAL_SCREENSHOTS.is_dir():
        return []
    return sorted(path for path in REAL_SCREENSHOTS.iterdir() if is_image_path(path))


@pytest.mark.parametrize("path", real_screenshot_cases(), ids=lambda path: path.name)
def test_r9_5_real_screenshots(path: Path) -> None:
    expected = read_puzzle_file(path.with_suffix(".txt"))
    assert import_screenshot(path).puzzle == canonical(expected)


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

    session = GameSession.from_file(save(draw_screenshot(EXAMPLE), tmp_path / "example.png"))
    assert session.puzzle == EXAMPLE
    assert color_distance(session.colors["A"], TEST_COLORS[0]) <= 3
    assert session.message == IMPORTED_MESSAGE
