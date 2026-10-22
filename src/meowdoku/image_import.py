"""Read a puzzle from a screenshot of a Meowdoku board (R9, docs/algorithm.md).

Pipeline: find the board's dark outer frame, count the cells from the grid
lines, read each cell's most common color, and group the colors into regions.
Cats and ✕ marks cover only part of a cell, so they are ignored (R9.1a).

Pillow is optional (the `[image]` extra) and imported only when needed (R9.2).
The constants below are tuned on synthetic images; retune them on the real
screenshots in tests/fixtures/screenshots/ (R9.5).
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING

from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import MAX_SIZE, Cell, MeowdokuError, Puzzle

if TYPE_CHECKING:
    from PIL.Image import Image

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
INSTALL_HINT = 'python -m pip install -e ".[image]"'

WHITE = (255, 255, 255)
TILE_CONTRAST = 40  # channel difference that separates a tile from white or the page
SQUARE_TOLERANCE = 0.1  # allowed width/height mismatch of the board
EDGE_STRENGTH = 20  # RGB distance that counts as a sharp color change between tiles
EDGE_SAMPLES = 60  # rows (or columns) sampled when looking for the gaps between tiles
CELL_BAND = (0.15, 0.2)  # sample this far inside each cell edge: clear of gaps, corners, and icons
SAMPLES_PER_SIDE = 12  # color samples along each side of a cell
COLOR_BIN = 12  # colors closer than this per channel count as the same color
COLOR_TOLERANCE = 28  # max RGB distance between cells of one region

RGB = tuple[int, int, int]
LabelGrid = list[list[str]]


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


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def import_screenshot(path: Path) -> ImportedPuzzle:
    """Read a screenshot into a validated puzzle plus region colors (R9.1).

    Raises OSError if the file can't be read, ImageImportError if no board is
    found, and PuzzleValidationError if the detected grid isn't a valid puzzle.
    """
    image = _open_image(path)
    board = find_board(image)
    size = count_cells(image, board)
    cell_colors = [
        [cell_color(image, cell_box(board, size, (row, col))) for col in range(size)]
        for row in range(size)
    ]
    labels, colors = group_colors(cell_colors, size)
    text = "\n".join("".join(row) for row in labels)
    return ImportedPuzzle(parse_puzzle(text), text, colors)


def _open_image(path: Path) -> "Image":
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        raise MeowdokuError(f"screenshot import needs Pillow; install it with: {INSTALL_HINT}") from None
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except UnidentifiedImageError:
        raise ImageImportError(f"{path.name} is not a readable PNG or JPEG image") from None


# Step 1: find the board


def find_board(image: "Image") -> Box:
    """Find the grid of colored tiles.

    In Meowdoku the board is a white card of rounded, colored tiles with white
    gaps between them, on a plain page background. Tile pixels are the ones
    far from both white and the page color; the board is the box around them.
    """
    background = _page_color(image)
    tiles = _darker(_far_from(image, WHITE), _far_from(image, background))
    extent = tiles.getbbox()
    if extent is None:
        raise ImageImportError("couldn't find the board: no colored tiles were found")
    board = Box(*extent)
    if abs(board.width - board.height) > SQUARE_TOLERANCE * max(board.width, board.height):
        raise ImageImportError(
            f"couldn't find the board: the colored area is {board.width}x{board.height} pixels, "
            "not square; crop the screenshot closer to the board"
        )
    return board


def _page_color(image: "Image") -> RGB:
    """The page background: the most common color among the image's corners."""
    width, height = image.size
    pixels = image.load()
    corners = [pixels[x, y][:3] for x in (0, width - 1) for y in (0, height - 1)]
    return Counter(corners).most_common(1)[0][0]


def _far_from(image: "Image", color: RGB) -> "Image":
    """A mask that is white where some channel differs from `color` by more than TILE_CONTRAST."""
    from PIL import Image, ImageChops

    difference = ImageChops.difference(image, Image.new("RGB", image.size, color))
    red, green, blue = difference.split()
    largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return largest.point(lambda value: 255 if value > TILE_CONTRAST else 0)


def _darker(first: "Image", second: "Image") -> "Image":
    """Pixelwise AND of two masks."""
    from PIL import ImageChops

    return ImageChops.darker(first, second)


# Step 2: count the cells


def count_cells(image: "Image", board: Box) -> int:
    """Board size N from the spacing of the grid lines in both directions."""
    pixels = image.load()
    xs = range(board.left, board.right)
    ys = range(board.top, board.bottom)
    across_lines = [[pixels[x, y] for x in xs] for y in _sample_positions(board.top, board.bottom)]
    down_lines = [[pixels[x, y] for y in ys] for x in _sample_positions(board.left, board.right)]
    across, down = _cells_along(across_lines), _cells_along(down_lines)
    if across != down:
        raise ImageImportError(f"found a grid {across} cells wide and {down} cells tall; the board must be square")
    if not 1 <= across <= MAX_SIZE:
        raise ImageImportError(f"found {across} cells per row; boards must have 1 to {MAX_SIZE}")
    return across


def _sample_positions(start: int, end: int) -> list[int]:
    """Up to EDGE_SAMPLES evenly spread pixel positions between start and end."""
    count = min(EDGE_SAMPLES, end - start)
    return [start + i * (end - start) // count for i in range(count)]


def _cells_along(lines: list[list[RGB]]) -> int:
    """Count cells along one direction from where the color changes sharply.

    `lines` are pixel colors read straight across the board. Grid lines cross
    every one of them, while cats and ✕ marks cross only some, so the median
    over lines keeps grid lines and drops marks. A change counts if it is
    within a few pixels, because a thick region border and the thin grid line
    it continues don't change color at exactly the same pixel.
    """
    length = len(lines[0])
    gap = max(3, length // (3 * MAX_SIZE))
    nearby_changes = [_nearby_changes(line, gap // 2) for line in lines]
    strength = [median(changes[i] for changes in nearby_changes) for i in range(length)]
    peaks = [i for i, value in enumerate(strength) if value >= EDGE_STRENGTH]
    centers = [
        center
        for group in _consecutive_groups(peaks, gap)
        if gap <= (center := sum(group) / len(group)) <= length - gap
    ]
    if not centers:
        return 1
    boundaries = [0.0, *centers, float(length)]
    cell_length = median(b - a for a, b in zip(boundaries, boundaries[1:]))
    return round(length / cell_length)


def _nearby_changes(line: list[RGB], radius: int) -> list[float]:
    """For each pixel, the largest color change between neighbors within `radius`."""
    changes = [0.0] + [_distance(a, b) for a, b in zip(line, line[1:])]
    return [max(changes[max(0, i - radius) : i + radius + 1]) for i in range(len(line))]


def _consecutive_groups(indexes: list[int], gap: int) -> list[list[int]]:
    """Split sorted indexes into groups wherever the next one is more than `gap` away."""
    groups: list[list[int]] = []
    for index in indexes:
        if groups and index - groups[-1][-1] <= gap:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


# Step 3: read each cell's color


def cell_box(board: Box, size: int, cell: Cell) -> Box:
    row, col = cell
    return Box(
        board.left + col * board.width // size,
        board.top + row * board.height // size,
        board.left + (col + 1) * board.width // size,
        board.top + (row + 1) * board.height // size,
    )


def cell_color(image: "Image", box: Box) -> RGB:
    """The most common color in a band just inside the cell's edges.

    Cat and ✕ icons sit in the middle of the cell, so sampling near the edges
    (but clear of the grid lines) reads the region color (R9.1a).
    """
    pixels = image.load()
    samples: list[RGB] = []
    for inset in CELL_BAND:
        for i in range(SAMPLES_PER_SIDE):
            along = inset + (1 - 2 * inset) * i / (SAMPLES_PER_SIDE - 1)
            for fx, fy in ((along, inset), (along, 1 - inset), (inset, along), (1 - inset, along)):
                x = min(box.right - 1, box.left + int(fx * box.width))
                y = min(box.bottom - 1, box.top + int(fy * box.height))
                samples.append(pixels[x, y][:3])
    bins = Counter(_color_bin(color) for color in samples)
    most_common_bin = bins.most_common(1)[0][0]
    members = [color for color in samples if _color_bin(color) == most_common_bin]
    return _average(members)


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
        raise ImageImportError(f"found {len(groups)} region colors; expected {size}")
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
