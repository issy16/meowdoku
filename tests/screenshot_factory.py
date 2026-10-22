"""Draw synthetic Meowdoku screenshots with known regions for import tests.

The style copies the real game (tests/fixtures/screenshots/IMG_7128.jpg): a
beige page, a white rounded card, and rounded colored tiles with white gaps,
measured at 105 px tiles, 9 px gaps, and about 8 px corner radius.

Requires Pillow; only test_image_import.py imports this module.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from meowdoku.puzzle import Cell, Puzzle

# The 10 tile colors read from the real screenshot, plus 2 more, pairwise at
# least 60 apart in RGB so different regions never merge.
TEST_COLORS = (
    "#9dd387", "#eb9fe0", "#9e704f", "#f6da90", "#5aa6bd", "#eda068",
    "#c7a635", "#877ad4", "#488b58", "#c77490", "#2828ac", "#dc28f4",
)
PAGE_COLOR = "#f6f2ef"
CARD_COLOR = "#ffffff"
MARK_COLOR = "#2b2b2b"
GAP_SHARE = 0.08  # gap between tiles, as a share of the cell pitch
RADIUS_SHARE = 0.08  # tile corner radius, as a share of the tile


def draw_screenshot(
    puzzle: Puzzle,
    *,
    cell: int = 60,
    origin: tuple[int, int] = (40, 60),
    marks: dict[Cell, str] | None = None,
) -> Image.Image:
    """A cropped screenshot of the board: page margin, white card, tiles."""
    size = puzzle.size
    gap = max(2, round(GAP_SHARE * cell))
    tile = cell - gap
    radius = max(1, round(RADIUS_SHARE * tile))
    left, top = origin
    board = size * cell - gap
    padding = 2 * gap
    width, height = 2 * left + board, 2 * top + board
    image = Image.new("RGB", (width, height), PAGE_COLOR)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (left - padding, top - padding, left + board + padding - 1, top + board + padding - 1),
        radius=3 * radius,
        fill=CARD_COLOR,
    )

    colors = {label: TEST_COLORS[i] for i, label in enumerate(puzzle.region_labels)}
    for row, col in puzzle.cells():
        x, y = left + col * cell, top + row * cell
        color = colors[puzzle.region_of((row, col))]
        draw.rounded_rectangle((x, y, x + tile - 1, y + tile - 1), radius=radius, fill=color)

    for (row, col), mark in (marks or {}).items():
        x, y = left + col * cell, top + row * cell
        if mark == "cat":
            _draw_cat(draw, x, y, tile)
        else:
            _draw_cross(draw, x, y, tile)
    return image


def _draw_cat(draw: ImageDraw.ImageDraw, x: int, y: int, tile: int) -> None:
    def at(fx: float, fy: float) -> tuple[float, float]:
        return (x + fx * tile, y + fy * tile)

    draw.polygon([at(0.24, 0.50), at(0.27, 0.16), at(0.47, 0.34)], fill=MARK_COLOR)
    draw.polygon([at(0.76, 0.50), at(0.73, 0.16), at(0.53, 0.34)], fill=MARK_COLOR)
    draw.ellipse([at(0.22, 0.28), at(0.78, 0.82)], fill=MARK_COLOR)


def _draw_cross(draw: ImageDraw.ImageDraw, x: int, y: int, tile: int) -> None:
    a, b = 0.32 * tile, 0.68 * tile
    draw.line((x + a, y + a, x + b, y + b), fill=MARK_COLOR, width=3)
    draw.line((x + a, y + b, x + b, y + a), fill=MARK_COLOR, width=3)


def save(image: Image.Image, path: Path, quality: int = 85) -> Path:
    if path.suffix.lower() in (".jpg", ".jpeg"):
        image.save(path, quality=quality)
    else:
        image.save(path)
    return path


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
