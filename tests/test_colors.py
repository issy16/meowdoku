import pytest

from meowdoku.colors import color_name, name_regions, region_phrases
from meowdoku.game import PALETTE

# Tile colors read from the real screenshot (IMG_7128.jpg) by image import.
REAL_GAME_COLORS = {
    "A": "#9dd387", "B": "#eb9fe0", "C": "#9e704f", "D": "#f6da90", "E": "#5aa6bd",
    "F": "#eda068", "G": "#c7a635", "H": "#877ad4", "I": "#488b58", "J": "#c77490",
}


def test_r7_8_real_game_colors_get_plain_unique_names() -> None:
    names = [color_name(color) for color in REAL_GAME_COLORS.values()]
    assert names == [
        "light green", "pink", "brown", "yellow", "blue",
        "orange", "mustard", "purple", "dark green", "rose",
    ]


def test_r7_8_gui_palette_names_are_unique() -> None:
    names = [color_name(color) for color in PALETTE]
    assert len(set(names)) == len(PALETTE)


@pytest.mark.parametrize(
    ("color", "name"),
    [("#ff0000", "red"), ("#00a000", "green"), ("#2080e0", "blue"), ("#fefefe", "white"), ("#202020", "black")],
)
def test_basic_colors(color: str, name: str) -> None:
    assert color_name(color) == name


def test_r7_8_slightly_off_colors_keep_their_name() -> None:
    """Screenshot colors vary a little with JPEG compression."""
    assert color_name("#a0d088") == "light green"
    assert color_name("#e8a2dd") == "pink"


def test_phrases_use_color_names() -> None:
    assert region_phrases({"A": "#eb9fe0", "B": "#9e704f"}) == {
        "A": "the pink region",
        "B": "the brown region",
    }


def test_r7_8_same_color_name_keeps_the_letter() -> None:
    assert region_phrases({"A": "#e53935", "B": "#f4a7a3", "C": "#9e704f"}) == {
        "A": "region 'A' (red)",
        "B": "region 'B' (red)",
        "C": "the brown region",
    }


PHRASES = {"A": "the pink region", "B": "the brown region"}


def test_name_regions_in_the_middle_of_a_sentence() -> None:
    message = "Every cell left in column 5 is in region 'B', so the cat of region 'B' must be in column 5."
    assert name_regions(message, PHRASES) == (
        "Every cell left in column 5 is in the brown region, so the cat of the brown region must be in column 5."
    )


def test_name_regions_at_the_start_of_a_sentence() -> None:
    message = "Region 'A' has only one cell left that can hold its cat."
    assert name_regions(message, PHRASES) == "The pink region has only one cell left that can hold its cat."


def test_name_regions_with_several_regions() -> None:
    message = "Every cell left in region 'A' and region 'B' is in rows 1 and 2."
    assert name_regions(message, PHRASES) == (
        "Every cell left in the pink region and the brown region is in rows 1 and 2."
    )


def test_unknown_labels_and_other_text_are_left_alone() -> None:
    message = "Row 2 has no cat; region 'Z' and the region near it."
    assert name_regions(message, PHRASES) == message
