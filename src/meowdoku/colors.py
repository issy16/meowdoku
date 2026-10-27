"""Plain color names for regions, so hints can say "the pink region" (R7.8)."""

import re
from collections import Counter
from collections.abc import Mapping

from meowdoku.messages import DEFAULT_LANGUAGE, color_region, shades

# Named reference colors. A region gets the name of the closest one.
NAMED_COLORS: tuple[tuple[str, str], ...] = (
    # Tile colors measured from the real game (tests/fixtures/screenshots/IMG_7128.jpg)
    ("light green", "#9dd387"),
    ("pink", "#eb9fe0"),
    ("brown", "#9e704f"),
    ("yellow", "#f6da90"),
    ("blue", "#5aa6bd"),
    ("orange", "#eda068"),
    ("mustard", "#c7a635"),
    ("purple", "#877ad4"),
    ("dark green", "#488b58"),
    ("rose", "#c77490"),
    # The extra colors of the GUI palette (game.PALETTE) not named elsewhere here
    ("cyan", "#00bcd4"),
    ("maroon", "#8e2430"),
    ("lime", "#aeea00"),
    # Softer colors
    ("red", "#f4a7a3"),
    ("green", "#a8d5ba"),
    ("blue", "#a7c7f4"),
    ("yellow", "#f9d98c"),
    ("purple", "#c9b3f2"),
    ("orange", "#f7c19b"),
    ("teal", "#9fdcdc"),
    ("lime", "#e0e48f"),
    ("pink", "#f2b5d8"),
    ("gray", "#bfc9d9"),
    ("tan", "#d9b99b"),
    ("light green", "#b5e3a1"),
    ("sky blue", "#8fc1e3"),
    ("coral", "#e8a0a0"),
    ("pale blue", "#cfe8f7"),
    ("beige", "#d4c4a8"),
    # Basic colors for anything else
    ("red", "#e53935"),
    ("green", "#43a047"),
    ("blue", "#1e88e5"),
    ("navy", "#283593"),
    ("magenta", "#e040fb"),
    ("crimson", "#d81b60"),
    ("teal", "#00897b"),
    ("gray", "#9e9e9e"),
    ("white", "#ffffff"),
    ("black", "#212121"),
)

_REGION_MENTION = re.compile(r"\b([Rr])egion '([^']+)'")


def _rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def color_name(color: str) -> str:
    """The name of the closest reference color, for a '#rrggbb' color."""
    rgb = _rgb(color)

    def distance(entry: tuple[str, str]) -> int:
        return sum((a - b) ** 2 for a, b in zip(rgb, _rgb(entry[1])))

    return min(NAMED_COLORS, key=distance)[0]


def region_phrases(colors: Mapping[str, str], language: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """How to mention each region: 'the pink region', in `language` (R12.4).

    Regions whose colors get the same name are told apart by shade, lightest
    first: "the lighter orange region" and "the darker orange region", or
    "the lightest", "the second-lightest", ... "the darkest" for three or
    more. Letters are never shown, so a hint is never ambiguous.
    """
    names = {label: color_name(color) for label, color in colors.items()}
    counts = Counter(names.values())
    phrases = {label: color_region(name, language) for label, name in names.items() if counts[name] == 1}
    for name in (name for name, count in counts.items() if count > 1):
        same = sorted((label for label in names if names[label] == name), key=lambda label: -_lightness(colors[label]))
        for shade, label in zip(shades(len(same), language), same):
            phrases[label] = color_region(name, language, shade)
    return {label: phrases[label] for label in colors}


def _lightness(color: str) -> float:
    red, green, blue = _rgb(color)
    return 0.299 * red + 0.587 * green + 0.114 * blue


def name_regions(message: str, phrases: Mapping[str, str]) -> str:
    """Replace mentions like "region 'A'" in a message with color phrases."""

    def replace(match: re.Match[str]) -> str:
        phrase = phrases.get(match.group(2))
        if phrase is None:
            return match.group(0)
        if match.group(1) == "R":
            return phrase[0].upper() + phrase[1:]
        return phrase

    return _REGION_MENTION.sub(replace, message)
