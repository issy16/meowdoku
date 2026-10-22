"""Draw the app icon, a cat on a board of Meowdoku tiles, as a macOS .icns file.

Usage: python packaging/make_icon.py OUTPUT.icns  (needs macOS's iconutil)
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Tile colors measured from the real game (see src/meowdoku/colors.py).
TILE_COLORS = (
    "#9dd387", "#eb9fe0", "#f6da90",
    "#5aa6bd", "#eda068", "#877ad4",
    "#c77490", "#c7a635", "#488b58",
)
CAT_FUR = "#262626"
CAT_FACE = "#ffffff"
SIZE = 1024


def draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = SIZE * 0.08
    draw.rounded_rectangle(
        (margin, margin, SIZE - margin, SIZE - margin), radius=SIZE * 0.18, fill="#ffffff"
    )
    inner = margin + SIZE * 0.06
    pitch = (SIZE - 2 * inner) / 3
    gap = pitch * 0.08
    start = inner + gap / 2  # center the tiles: the last tile has no gap after it
    for index, color in enumerate(TILE_COLORS):
        row, col = divmod(index, 3)
        x, y = start + col * pitch, start + row * pitch
        draw.rounded_rectangle((x, y, x + pitch - gap, y + pitch - gap), radius=pitch * 0.12, fill=color)
    _draw_cat(draw, start + pitch, start + pitch, pitch - gap)
    return image


def _draw_cat(draw: ImageDraw.ImageDraw, x: float, y: float, tile: float) -> None:
    def at(fx: float, fy: float) -> tuple[float, float]:
        return (x + fx * tile, y + fy * tile)

    draw.polygon([at(0.14, 0.50), at(0.20, 0.06), at(0.44, 0.24)], fill=CAT_FUR)
    draw.polygon([at(0.86, 0.50), at(0.80, 0.06), at(0.56, 0.24)], fill=CAT_FUR)
    draw.ellipse([at(0.10, 0.16), at(0.90, 0.92)], fill=CAT_FUR)
    draw.ellipse([at(0.26, 0.50), at(0.74, 0.90)], fill=CAT_FACE)
    for cx in (0.36, 0.64):
        draw.ellipse([at(cx - 0.08, 0.40), at(cx + 0.08, 0.56)], fill=CAT_FACE)
        draw.ellipse([at(cx - 0.04, 0.44), at(cx + 0.04, 0.52)], fill=CAT_FUR)


def write_icns(icon: Image.Image, output: Path) -> None:
    """Save every size macOS wants into an .iconset folder, then convert it."""
    with tempfile.TemporaryDirectory() as folder:
        iconset = Path(folder) / "Meowdoku.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            icon.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            icon.resize((2 * size, 2 * size), Image.Resampling.LANCZOS).save(
                iconset / f"icon_{size}x{size}@2x.png"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)


if __name__ == "__main__":
    write_icns(draw_icon(), Path(sys.argv[1]))
