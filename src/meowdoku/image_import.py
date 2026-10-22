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

DARK_LUMINANCE = 100  # pixels darker than this can be part of the board frame
MIN_FRAME_FRACTION = 0.25  # the frame is at least this share of the image width
FRAME_SOLIDITY = 0.9  # share of a frame edge that must be dark
SQUARE_TOLERANCE = 0.1  # allowed width/height mismatch of the board
EDGE_STRENGTH = 20  # RGB distance that counts as a sharp color change at a grid line
EDGE_SAMPLES = 60  # rows (or columns) sampled when looking for grid lines
SCAN_FRACTIONS = (0.29, 0.41, 0.53, 0.67, 0.79)  # off-grid places to measure the border
CELL_BAND = (0.12, 0.17)  # sample this far inside each cell edge: clear of lines and icons
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
    gray = image.convert("L")
    board = find_board(gray)
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


# Step 1: find the board's outer frame


def find_board(gray: "Image") -> Box:
    """Find the largest square framed by dark lines, and return its inside."""
    lines = _horizontal_frame_lines(gray)
    frames = [
        frame
        for top_index, top in enumerate(lines)
        for bottom in lines[top_index + 1 :]
        if (frame := _frame_between(gray, top, bottom)) is not None
    ]
    if not frames:
        raise ImageImportError("couldn't find the board: no square grid with a dark border was found")
    outer = max(frames, key=lambda box: box.width * box.height)
    return _inside_of_frame(gray, outer)


@dataclass(frozen=True)
class _Line:
    """A horizontal dark line: its first and last pixel rows and its x extent."""

    first_row: int
    last_row: int
    left: int
    right: int


def _horizontal_frame_lines(gray: "Image") -> list[_Line]:
    """Groups of consecutive rows that each hold one long, solid dark run."""
    width, height = gray.size
    dark = gray.point(lambda value: 255 if value < DARK_LUMINANCE else 0)
    lines: list[_Line] = []
    for y in range(height):
        row = dark.crop((0, y, width, y + 1))
        extent = row.getbbox()
        if extent is None:
            continue
        left, _, right, _ = extent
        dark_count = row.histogram()[255]
        if right - left < MIN_FRAME_FRACTION * width or dark_count < FRAME_SOLIDITY * (right - left):
            continue
        previous = lines[-1] if lines else None
        if previous and previous.last_row == y - 1 and _close(previous.left, left) and _close(previous.right, right):
            lines[-1] = _Line(previous.first_row, y, previous.left, previous.right)
        else:
            lines.append(_Line(y, y, left, right))
    return lines


def _frame_between(gray: "Image", top: _Line, bottom: _Line) -> Box | None:
    """The box framed by two horizontal lines, if it's square and has dark sides."""
    if not (_close(top.left, bottom.left) and _close(top.right, bottom.right)):
        return None
    box = Box(top.left, top.first_row, top.right, bottom.last_row + 1)
    if abs(box.width - box.height) > SQUARE_TOLERANCE * box.width:
        return None
    for x in (box.left, box.right - 1):
        side = gray.crop((x, box.top, x + 1, box.bottom))
        dark_share = sum(1 for value in side.tobytes() if value < DARK_LUMINANCE) / box.height
        if dark_share < FRAME_SOLIDITY:
            return None
    return box


def _inside_of_frame(gray: "Image", frame: Box) -> Box:
    """Step inward from each side of the frame until past the dark border.

    Several scan lines are used, placed off the middle so they don't run
    along a grid line, and the thinnest border reading wins.
    """
    pixels = gray.load()

    def border_thickness(start: tuple[int, int], step: tuple[int, int], limit: int) -> int:
        x, y = start
        dx, dy = step
        thickness = 0
        while thickness < limit and pixels[x + dx * thickness, y + dy * thickness] < DARK_LUMINANCE:
            thickness += 1
        return thickness

    def thinnest(starts: list[tuple[int, int]], step: tuple[int, int], limit: int) -> int:
        return min(border_thickness(start, step, limit) for start in starts)

    ys = [frame.top + int(f * frame.height) for f in SCAN_FRACTIONS]
    xs = [frame.left + int(f * frame.width) for f in SCAN_FRACTIONS]
    half_width, half_height = frame.width // 2, frame.height // 2
    left = frame.left + thinnest([(frame.left, y) for y in ys], (1, 0), half_width)
    right = frame.right - thinnest([(frame.right - 1, y) for y in ys], (-1, 0), half_width)
    top = frame.top + thinnest([(x, frame.top) for x in xs], (0, 1), half_height)
    bottom = frame.bottom - thinnest([(x, frame.bottom - 1) for x in xs], (0, -1), half_height)
    return Box(left, top, right, bottom)


def _close(a: int, b: int, tolerance: int = 3) -> bool:
    return abs(a - b) <= tolerance


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
