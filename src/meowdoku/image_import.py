"""Read a puzzle, and any cats and ✕ marks, from a Meowdoku screenshot (R9).

Two kinds of screenshot are read (R9.6): the Meowdoku game's, and this
program's own window (gui.py). Both draw the board as rounded colored tiles
with white gaps, on a white card on a plain page, and a ✕ as a thick white X
on a tile. A cat covers most of a tile: in the game, a black and white cat
face; in the window, a white lucky cat face with dark outlines. The window
also shows Solve's answer as gray-outlined cats; those aren't the player's
marks, so they read as empty (see tests/fixtures/screenshots/).

Pipeline (docs/algorithm.md): find the tiles, count them, read each tile's
color, group colors into regions, and read the mark on each tile.

Uses Pillow, the project's one runtime dependency (NFR1).
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from PIL import Image, ImageChops, UnidentifiedImageError

from meowdoku.messages import Message
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import MAX_SIZE, Cell, MeowdokuError, Puzzle
from meowdoku.state import Mark

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})

RGB = tuple[int, int, int]
LabelGrid = list[list[str]]

WHITE = (255, 255, 255)
TILE_CONTRAST = 40  # channel difference that separates a tile from white or the page
SQUARE_TOLERANCE = 0.1  # allowed width/height mismatch of the board
MIN_ROW_COVERAGE = 0.3  # share of a row that is tiles, for a row through the board
# A weaker row between two such rows still crosses the board if it's at least this covered:
# it runs through marked tiles, while a gap between tiles is white
WEAK_ROW_COVERAGE = 0.04
BRIDGE_SHARE = 0.3  # bridge a gap at most this share of the row runs on both sides
GAP_COVERAGE = 0.25  # a pixel column (or row) this little covered by tiles is a gap
CELL_INSET = 0.08  # skip this share of each cell edge: the white gap around the tile
CELL_SAMPLES = 16  # color samples per cell, per direction
WHITE_MIN = 225  # every channel above this: white (gaps, ✕ marks, cat faces)
BLACK_MAX = 80  # every channel below this: black (cat fur and outlines)
GRAY_SPREAD = 10  # channels at most this far apart, between black and white: neutral gray
MARK_AREA = (0.25, 0.75)  # the middle of a tile, where marks are read
CAT_SHARE = 0.12  # this much black in the middle of a tile means a cat
# This much gray means a Solve cat in the window (measured 0.27 or more; ✕ marks 0.05 or less)
SOLUTION_CAT_SHARE = 0.15
CROSS_SHARE = 0.12  # this much white in the middle of a tile means a ✕
COLOR_BIN = 12  # colors closer than this per channel count as the same color
COLOR_TOLERANCE = 28  # max RGB distance between cells of one region
# The window's hint (orange) and problem (red) rings: as drawn (gui.HIGHLIGHT_COLORS), and as
# macOS screenshots show them after color matching (measured on the gui-* fixtures).
HIGHLIGHT_RING_COLORS: tuple[RGB, ...] = ((0xF5, 0xA7, 0x00), (0xD6, 0x28, 0x28))
SCREENSHOT_RING_COLORS: tuple[RGB, ...] = ((234, 169, 59), (197, 58, 50))
# Rings are left out within this much of their colors. It's tighter than TILE_CONTRAST:
# the game's mustard tile (205, 164, 0) is exactly 40 from the drawn orange, and the
# closest game tile to any ring color is 33 from it (IMG_7117's orange).
RING_CONTRAST = 24



class ImageImportError(MeowdokuError):
    """A screenshot couldn't be turned into a puzzle (R9.4)."""


@dataclass(frozen=True)
class Box:
    """A pixel rectangle; right and bottom are exclusive."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class ImportedPuzzle:
    puzzle: Puzzle
    text: str
    colors: dict[str, str]
    """Each region label's color as '#rrggbb' (R8.3)."""
    cats: frozenset[Cell] = frozenset()
    crosses: frozenset[Cell] = frozenset()

    @property
    def marks_text(self) -> str:
        """The marks read, one line per row: `*` cat, `x` ✕, `.` empty."""
        return "\n".join(
            "".join(
                "*" if (row, col) in self.cats else "x" if (row, col) in self.crosses else "."
                for col in range(self.puzzle.size)
            )
            for row in range(self.puzzle.size)
        )


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def import_screenshot(path: Path) -> ImportedPuzzle:
    """Read a screenshot into a validated puzzle, its colors, and its marks (R9.1).

    Raises OSError if the file can't be read, ImageImportError if it isn't a
    screenshot or no board is found, and PuzzleValidationError if the detected
    grid isn't a valid puzzle.
    """
    if not is_image_path(path):
        raise ImageImportError(Message("err.not_screenshot", name=path.name))
    image = _open_image(path)
    tiles = tile_mask(image)
    board = find_board(tiles)
    size = count_cells(tiles, board)
    boxes = {(row, col): cell_box(board, size, (row, col)) for row in range(size) for col in range(size)}

    cell_colors = [[cell_color(image, boxes[(row, col)]) for col in range(size)] for row in range(size)]
    labels, colors = group_colors(cell_colors, size)
    text = "\n".join("".join(row) for row in labels)

    marks = {cell: read_mark(image, box) for cell, box in boxes.items()}
    cats = frozenset(cell for cell, mark in marks.items() if mark is Mark.CAT)
    crosses = frozenset(cell for cell, mark in marks.items() if mark is Mark.CROSS)
    return ImportedPuzzle(parse_puzzle(text), text, colors, cats, crosses)


def _open_image(path: Path) -> Image.Image:
    """Open the image as RGB, laying any transparency over white.

    A macOS window screenshot is transparent around the window's shadow.
    """
    try:
        with Image.open(path) as image:
            if image.mode in ("RGBA", "LA", "P"):
                rgba = image.convert("RGBA")
                return Image.alpha_composite(Image.new("RGBA", rgba.size, WHITE), rgba).convert("RGB")
            return image.convert("RGB")
    except UnidentifiedImageError:
        raise ImageImportError(Message("err.unreadable", name=path.name)) from None


# Step 1: find the board


def tile_mask(image: Image.Image) -> Image.Image:
    """A mask of tile pixels: far from white, the page color, and the window's ring colors.

    White gaps, white ✕ marks, and the white parts of cat faces are not
    tiles, and neither are the window's hint and problem rings, which lie in
    the gaps around tiles.
    """
    mask = _darker(_far_from(image, WHITE), _far_from(image, _page_color(image)))
    for ring in HIGHLIGHT_RING_COLORS + SCREENSHOT_RING_COLORS:
        mask = _darker(mask, _far_from(image, ring, RING_CONTRAST))
    return mask


def find_board(tiles: Image.Image) -> Box:
    """Find the grid of tiles, even in a full phone screenshot.

    Rows that are mostly tile pixels form horizontal bands. The thin white gaps
    between tile rows are bridged, so the whole board is one band. Headers,
    icons, buttons, and ad banners make short, wide bands; the board is the
    largest band whose tile area is square.
    """
    if tiles.getbbox() is None:
        raise ImageImportError(Message("err.no_tiles"))
    height = tiles.height
    coverage = tiles.resize((1, height), Image.Resampling.BOX).tobytes()
    bands = _bridge_small_gaps(_tile_runs(coverage))
    boards = [box for top, bottom in bands if (box := _square_box(tiles, top, bottom))]
    if not boards:
        raise ImageImportError(Message("err.no_grid"))
    return max(boards, key=lambda box: box.width * box.height)


def _tile_runs(coverage: bytes) -> list[list[int]]:
    """Runs of pixel lines (rows or columns) that cross tiles, from each line's tile coverage.

    A line belongs to a run when at least MIN_ROW_COVERAGE of it is tiles.
    Weaker lines between two runs join them when none of those lines is
    nearly empty: they cross tiles covered by marks (a row of cat faces and
    ✕ marks), not the white gap between tiles. This matters when the board
    fills only part of the image width, as in a wide window screenshot.
    """
    strong = _consecutive_groups([i for i, value in enumerate(coverage) if value >= MIN_ROW_COVERAGE * 255], 2)
    runs: list[list[int]] = []
    for run in strong:
        between = range(runs[-1][-1] + 1, run[0]) if runs else range(0)
        if runs and all(coverage[i] >= WEAK_ROW_COVERAGE * 255 for i in between):
            runs[-1] = runs[-1] + list(between) + run
        else:
            runs.append(run)
    return runs


def _bridge_small_gaps(runs: list[list[int]]) -> list[tuple[int, int]]:
    """Join runs of rows into bands across gaps that are small next to the runs.

    The white gap between two tile rows is small compared with the tiles on
    either side, at any board size or image scale. The space between the
    board and other screen parts is not.
    """
    bands: list[tuple[int, int]] = []
    previous_run_height = 0
    for run in runs:
        top, bottom, height = run[0], run[-1] + 1, len(run)
        if bands:
            band_top, band_bottom = bands[-1]
            if top - band_bottom <= BRIDGE_SHARE * min(previous_run_height, height):
                bands[-1] = (band_top, bottom)
                previous_run_height = height
                continue
        bands.append((top, bottom))
        previous_run_height = height
    return bands


def _square_box(tiles: Image.Image, top: int, bottom: int) -> Box | None:
    """The box around the board's tiles between two rows, if it is square.

    Columns are banded like rows, and the widest band is the board, so tile
    pixels off to the side (a window's shadow, say) don't widen it.
    """
    band = tiles.crop((0, top, tiles.width, bottom))
    coverage = band.resize((tiles.width, 1), Image.Resampling.BOX).tobytes()
    column_bands = _bridge_small_gaps(_tile_runs(coverage))
    if not column_bands:
        return None
    left, right = max(column_bands, key=lambda column_band: column_band[1] - column_band[0])
    extent = tiles.crop((left, top, right, bottom)).getbbox()
    if extent is None:
        return None
    band_left, band_top, band_right, band_bottom = extent
    box = Box(left + band_left, top + band_top, left + band_right, top + band_bottom)
    if abs(box.width - box.height) > SQUARE_TOLERANCE * max(box.width, box.height):
        return None
    return box


def _page_color(image: Image.Image) -> RGB:
    """The page background: the most common color among the image's corners."""
    width, height = image.size
    pixels = image.load()
    corners = [pixels[x, y][:3] for x in (0, width - 1) for y in (0, height - 1)]
    return Counter(corners).most_common(1)[0][0]


def _far_from(image: Image.Image, color: RGB, contrast: int = TILE_CONTRAST) -> Image.Image:
    """A mask that is white where some channel differs from `color` by more than `contrast`."""
    difference = ImageChops.difference(image, Image.new("RGB", image.size, color))
    red, green, blue = difference.split()
    largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return largest.point(lambda value: 255 if value > contrast else 0)


def _darker(first: Image.Image, second: Image.Image) -> Image.Image:
    """Pixelwise AND of two masks."""
    return ImageChops.darker(first, second)


# Step 2: count the cells


def count_cells(tiles: Image.Image, board: Box) -> int:
    """Board size N from the spacing of the white gaps in both directions."""
    inside = tiles.crop((board.left, board.top, board.right, board.bottom))
    across = _cells_along(inside.resize((board.width, 1), Image.Resampling.BOX).tobytes())
    down = _cells_along(inside.resize((1, board.height), Image.Resampling.BOX).tobytes())
    if across != down:
        raise ImageImportError(Message("err.not_square", across=across, down=down))
    if not 1 <= across <= MAX_SIZE:
        raise ImageImportError(Message("err.size", across=across, max=MAX_SIZE))
    return across


def _cells_along(coverage: bytes) -> int:
    """Count cells along one direction from how much of each pixel line is tiles.

    A gap between tiles is white along the whole board, so its coverage is
    near zero. A ✕ or a cat face covers only part of any line through a tile,
    so tiles stay well covered even when every tile has a mark.
    """
    length = len(coverage)
    gaps = [index for index, value in enumerate(coverage) if value < GAP_COVERAGE * 255]
    centers = [sum(group) / len(group) for group in _consecutive_groups(gaps, 2)]
    if not centers:
        return 1
    boundaries = [0.0, *centers, float(length)]
    cell_length = median(b - a for a, b in zip(boundaries, boundaries[1:]))
    return round(length / cell_length)


def _consecutive_groups(indexes: list[int], gap: int) -> list[list[int]]:
    """Split sorted indexes into groups wherever the next one is more than `gap` away."""
    groups: list[list[int]] = []
    for index in indexes:
        if groups and index - groups[-1][-1] <= gap:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


# Step 3: read each tile's color


def cell_box(board: Box, size: int, cell: Cell) -> Box:
    row, col = cell
    return Box(
        board.left + col * board.width // size,
        board.top + row * board.height // size,
        board.left + (col + 1) * board.width // size,
        board.top + (row + 1) * board.height // size,
    )


def _samples(image: Image.Image, box: Box, start: float, end: float, count: int) -> list[RGB]:
    """Colors on an evenly spaced count×count grid between two shares of the box."""
    pixels = image.load()
    colors = []
    for i in range(count):
        for j in range(count):
            fx = start + (end - start) * i / (count - 1)
            fy = start + (end - start) * j / (count - 1)
            x = min(box.right - 1, box.left + int(fx * box.width))
            y = min(box.bottom - 1, box.top + int(fy * box.height))
            colors.append(pixels[x, y][:3])
    return colors


def cell_color(image: Image.Image, box: Box) -> RGB:
    """The tile's color: the most common color that isn't white, black, or gray.

    White (gaps, ✕ marks, cat faces), black (cat fur and outlines), and
    neutral gray (the outlines of Solve's cats in the window) are skipped, so
    the tile color still wins on tiles with marks.
    """
    samples = [
        color
        for color in _samples(image, box, CELL_INSET, 1 - CELL_INSET, CELL_SAMPLES)
        if not _is_white(color) and not _is_black(color) and not _is_gray(color)
    ]
    if not samples:
        raise ImageImportError(Message("err.tile_color"))
    bins = Counter(_color_bin(color) for color in samples)
    most_common_bin = bins.most_common(1)[0][0]
    return _average([color for color in samples if _color_bin(color) == most_common_bin])


def _is_white(color: RGB) -> bool:
    return min(color) > WHITE_MIN


def _is_black(color: RGB) -> bool:
    return max(color) < BLACK_MAX


def _is_gray(color: RGB) -> bool:
    """A neutral gray between black and white: all channels nearly equal."""
    return max(color) - min(color) <= GRAY_SPREAD and not _is_white(color) and not _is_black(color)


def _color_bin(color: RGB) -> RGB:
    red, green, blue = color
    return (red // COLOR_BIN, green // COLOR_BIN, blue // COLOR_BIN)


def _average(colors: list[RGB]) -> RGB:
    count = len(colors)
    red, green, blue = (round(sum(channel) / count) for channel in zip(*colors))
    return (red, green, blue)


# Step 4: group colors into regions


def group_colors(cell_colors: list[list[RGB]], size: int) -> tuple[LabelGrid, dict[str, str]]:
    """Label cells A, B, C… so that cells with similar colors share a label.

    Similar colors are joined in chains (single linkage). Labels follow first
    appearance in row-major order (R9.3).
    """
    cells = [(row, col) for row in range(size) for col in range(size)]
    color_of = {cell: cell_colors[cell[0]][cell[1]] for cell in cells}
    group_of = _link_similar(cells, color_of)

    groups = list(dict.fromkeys(group_of[cell] for cell in cells))
    if len(groups) != size:
        raise ImageImportError(Message("err.region_colors", found=len(groups), expected=size))
    label_of_group = {group: chr(ord("A") + index) for index, group in enumerate(groups)}

    labels = [[label_of_group[group_of[(row, col)]] for col in range(size)] for row in range(size)]
    colors = {
        label: _to_hex(_average([color_of[cell] for cell in cells if group_of[cell] == group]))
        for group, label in label_of_group.items()
    }
    return labels, colors


def _link_similar(cells: list[Cell], color_of: dict[Cell, RGB]) -> dict[Cell, Cell]:
    """Union-find: map each cell to a representative cell of its color group."""
    parent = {cell: cell for cell in cells}

    def root(cell: Cell) -> Cell:
        while parent[cell] != cell:
            parent[cell] = parent[parent[cell]]
            cell = parent[cell]
        return cell

    for index, first in enumerate(cells):
        for second in cells[index + 1 :]:
            if _distance(color_of[first], color_of[second]) <= COLOR_TOLERANCE:
                a, b = root(first), root(second)
                if a != b:
                    parent[max(a, b)] = min(a, b)
    return {cell: root(cell) for cell in cells}


def _distance(a: RGB, b: RGB) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _to_hex(color: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


# Step 5: read the marks (R9.1a)


def read_mark(image: Image.Image, box: Box) -> Mark | None:
    """Read the mark in the middle of a tile.

    Black there means a cat: the game cat's fur, or the window cat's outlines
    and eyes. Neutral gray means one of Solve's cats in the window, which
    isn't the player's mark. Otherwise white means a ✕. A tile with too little
    of any is left empty rather than guessed.
    """
    samples = _samples(image, box, *MARK_AREA, CELL_SAMPLES)

    def share(test: Callable[[RGB], bool]) -> float:
        return sum(test(color) for color in samples) / len(samples)

    if share(_is_black) >= CAT_SHARE:
        return Mark.CAT
    if share(_is_gray) >= SOLUTION_CAT_SHARE:
        return None
    if share(_is_white) >= CROSS_SHARE:
        return Mark.CROSS
    return None
