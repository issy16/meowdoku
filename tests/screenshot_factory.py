"""Draw synthetic Meowdoku screenshots with known regions for import tests.

Requires Pillow; only test_image_import.py imports this module.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from meowdoku.puzzle import Cell, Puzzle

# 12 light colors, pairwise at least 60 apart in RGB, including white and gray.
TEST_COLORS = (
    "#ff7878", "#78a5ff", "#ffff78", "#78ff78", "#ff78ff", "#dcdcdc",
    "#78ffe1", "#ffa5b4", "#a5a596", "#b4ffa5", "#c387d2", "#ffffff",
)
LINE_COLOR = "#9e9e9e"
BORDER_COLOR = "#222222"
MARK_COLOR = "#2b2b2b"


def draw_screenshot(
    puzzle: Puzzle,
    *,
    cell: int = 60,
    border: int = 4,
    origin: tuple[int, int] = (40, 180),
    marks: dict[Cell, str] | None = None,
    background: str = "#f7f3ee",
) -> Image.Image:
    """A phone-like screenshot: a dark header bar, the board, and text-like blocks below."""
    size = puzzle.size
    left, top = origin
    board = size * cell
    width, height = left * 2 + board, top + board + 260
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width - 1, 70), fill="#333333")
    for i in range(4):
        y = top + board + 60 + i * 40
        draw.rectangle((left, y, left + board * (i + 2) // 6, y + 14), fill="#444444")

    colors = {label: TEST_COLORS[i] for i, label in enumerate(puzzle.region_labels)}
    for row, col in puzzle.cells():
        x, y = left + col * cell, top + row * cell
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=colors[puzzle.region_of((row, col))])

    for i in range(1, size):
        draw.line((left + i * cell, top, left + i * cell, top + board - 1), fill=LINE_COLOR, width=1)
        draw.line((left, top + i * cell, left + board - 1, top + i * cell), fill=LINE_COLOR, width=1)

    half = border // 2
    for row, col in puzzle.cells():
        region = puzzle.region_of((row, col))
        x, y = left + col * cell, top + row * cell
        if col + 1 < size and puzzle.region_of((row, col + 1)) != region:
            draw.rectangle((x + cell - half, y, x + cell + half - 1, y + cell - 1), fill=BORDER_COLOR)
        if row + 1 < size and puzzle.region_of((row + 1, col)) != region:
            draw.rectangle((x, y + cell - half, x + cell - 1, y + cell + half - 1), fill=BORDER_COLOR)
    draw.rectangle(
        (left - border, top - border, left + board + border - 1, top + board + border - 1),
        outline=BORDER_COLOR,
        width=border,
    )

    for (row, col), mark in (marks or {}).items():
        x, y = left + col * cell, top + row * cell
        if mark == "cat":
            _draw_cat(draw, x, y, cell)
        else:
            _draw_cross(draw, x, y, cell)
    return image


def _draw_cat(draw: ImageDraw.ImageDraw, x: int, y: int, cell: int) -> None:
    def at(fx: float, fy: float) -> tuple[float, float]:
        return (x + fx * cell, y + fy * cell)

    draw.polygon([at(0.24, 0.50), at(0.27, 0.16), at(0.47, 0.34)], fill=MARK_COLOR)
    draw.polygon([at(0.76, 0.50), at(0.73, 0.16), at(0.53, 0.34)], fill=MARK_COLOR)
    draw.ellipse([at(0.22, 0.28), at(0.78, 0.82)], fill=MARK_COLOR)


def _draw_cross(draw: ImageDraw.ImageDraw, x: int, y: int, cell: int) -> None:
    a, b = 0.32 * cell, 0.68 * cell
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
