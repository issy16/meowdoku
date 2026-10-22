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
CROSS_COLOR = "#ffffff"
CAT_FUR = "#262626"
CAT_FACE = "#ffffff"
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
    """A black and white cat face over most of the tile, as in IMG_7117.PNG."""

    def at(fx: float, fy: float) -> tuple[float, float]:
        return (x + fx * tile, y + fy * tile)

    draw.polygon([at(0.14, 0.50), at(0.20, 0.06), at(0.44, 0.24)], fill=CAT_FUR)
    draw.polygon([at(0.86, 0.50), at(0.80, 0.06), at(0.56, 0.24)], fill=CAT_FUR)
    draw.ellipse([at(0.10, 0.16), at(0.90, 0.92)], fill=CAT_FUR)
    draw.ellipse([at(0.26, 0.50), at(0.74, 0.90)], fill=CAT_FACE)
    for cx in (0.36, 0.64):
        draw.ellipse([at(cx - 0.08, 0.40), at(cx + 0.08, 0.56)], fill=CAT_FACE)
        draw.ellipse([at(cx - 0.04, 0.44), at(cx + 0.04, 0.52)], fill=CAT_FUR)


def _draw_cross(draw: ImageDraw.ImageDraw, x: int, y: int, tile: int) -> None:
    """A thick white X with rounded ends, as in IMG_7117.PNG."""
    width = max(2, round(0.16 * tile))
    a, b = 0.24 * tile, 0.76 * tile
    for x0, y0, x1, y1 in ((a, a, b, b), (a, b, b, a)):
        draw.line((x + x0, y + y0, x + x1, y + y1), fill=CROSS_COLOR, width=width)
        for px, py in ((x0, y0), (x1, y1)):
            r = width / 2
            draw.ellipse((x + px - r, y + py - r, x + px + r, y + py + r), fill=CROSS_COLOR)


def save(image: Image.Image, path: Path, quality: int = 85) -> Path:
    if path.suffix.lower() in (".jpg", ".jpeg"):
        image.save(path, quality=quality)
    else:
        image.save(path)
    return path


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def add_phone_ui(board: Image.Image, seed: int = 0) -> Image.Image:
    """Surround a board screenshot with the app's other screen parts, as in IMG_7114.PNG.

    Header text, a fish pill, a rule card with small icons, round buttons
    with a red badge, and a multicolored ad banner. None of them is square.
    """
    import random

    rng = random.Random(seed)
    width = board.width
    top, bottom = int(0.55 * width), int(0.5 * width)
    image = Image.new("RGB", (width, top + board.height + bottom), PAGE_COLOR)
    image.paste(board, (0, top))
    draw = ImageDraw.Draw(image)
    w = width / 100

    # Header: "Level 218   Score 0" as dark text-like blocks
    for x0 in (30, 58):
        draw.rectangle((x0 * w, 14 * w, (x0 + 12) * w, 18 * w), fill="#8b5a4a")
        draw.rectangle((x0 * w, 20 * w, (x0 + 9) * w, 25 * w), fill="#8b5a4a")
    # Fish pill
    draw.rounded_rectangle((52 * w, 30 * w, 76 * w, 38 * w), radius=4 * w, fill=CARD_COLOR)
    for i in range(3):
        draw.ellipse(((55 + 6 * i) * w, 31 * w, (60 + 6 * i) * w, 37 * w), fill="#f5b400")
    # Rule card: white card with small beige squares, dark crosses, and text
    draw.rounded_rectangle((3 * w, 41 * w, 97 * w, 53 * w), radius=2 * w, fill=CARD_COLOR)
    for panel in range(3):
        x0 = (6 + 31 * panel) * w
        for i in range(3):
            for j in range(3):
                x, y = x0 + i * 2.6 * w, (43 + j * 2.6) * w
                draw.rectangle((x, y, x + 2.2 * w, y + 2.2 * w), fill="#e6c9b6")
                draw.line((x, y, x + 2.2 * w, y + 2.2 * w), fill="#7a4a3a", width=2)
        draw.rectangle((x0 + 9 * w, 45 * w, x0 + 24 * w, 47 * w), fill="#8b5a4a")

    y0 = top + board.height
    # Round buttons with a red badge
    for cx in (33, 67):
        draw.ellipse(((cx - 7) * w, y0 + 6 * w, (cx + 7) * w, y0 + 20 * w), fill=CARD_COLOR)
        draw.ellipse(((cx - 3) * w, y0 + 10 * w, (cx + 3) * w, y0 + 16 * w), fill="#2b2b2b")
    draw.ellipse((36 * w, y0 + 4 * w, 42 * w, y0 + 10 * w), fill="#e53935")
    # Ad banner: a wide strip of random colors
    for i in range(40):
        x = (10 + 2 * i) * w
        draw.rectangle((x, y0 + 26 * w, x + 2 * w, y0 + 38 * w), fill=tuple(rng.randrange(256) for _ in range(3)))
    return image
