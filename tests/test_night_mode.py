"""Night mode: the same two palettes in the web app and the desktop window, both easy to read (R13)."""

import re
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

import meowdoku.gui
from meowdoku.game import GameSession
from meowdoku.gui import LIGHT, NIGHT, ON_ACCENT, MeowdokuApp, Palette

STYLE = (Path(__file__).resolve().parent.parent / "web" / "style.css").read_text()
EXAMPLE = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"


def tokens(selector: str) -> dict[str, str]:
    """The --name: #rrggbb colors set in the first CSS block with this selector."""
    block = STYLE[STYLE.index(selector + " {") :]
    block = block[: block.index("}")]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


WEB_LIGHT = tokens(":root")
WEB_NIGHT = tokens(':root[data-theme="night"]')


def test_r13_2_auto_night_matches_chosen_night() -> None:
    assert tokens(":root:not([data-theme])") == WEB_NIGHT


@pytest.mark.parametrize(("palette", "web"), [(LIGHT, WEB_LIGHT), (NIGHT, WEB_NIGHT)])
def test_r13_1_desktop_and_web_use_the_same_colors(palette: Palette, web: dict[str, str]) -> None:
    assert (palette.page, palette.card, palette.text, palette.subtle, palette.border, palette.accent, palette.link) == (
        web["page"], web["card"], web["text"], web["subtle"], web["border"], web["accent"], web["apply"],
    )


@pytest.mark.parametrize("web", [WEB_LIGHT, WEB_NIGHT], ids=["light", "night"])
def test_r13_5_text_has_aa_contrast(web: dict[str, str]) -> None:
    for text in ("text", "subtle", "apply", "error"):
        for background in ("page", "card"):
            assert contrast(web[text], web[background]) >= 4.5, (text, background)
    assert contrast(ON_ACCENT, web["accent"]) >= 4.5


def test_r13_1_tiles_marks_and_rings_are_the_same_at_night() -> None:
    for name in ("cross", "cat-ink", "revealed-ink", "hint", "problem"):
        assert name not in WEB_NIGHT


# The desktop window (R13.4)


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    window.withdraw()
    yield window
    window.destroy()


def test_r13_4_appearance_menu_switches_and_is_remembered(
    root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(meowdoku.gui, "system_is_dark", lambda: False)
    settings = tmp_path / "settings.json"
    meowdoku.gui.save_language(settings, "ja")
    app = MeowdokuApp(root, GameSession.from_text(EXAMPLE), settings)
    assert app.theme == "auto" and app.palette is LIGHT
    app._theme.set("night")
    app._choose_theme()
    assert app.palette is NIGHT
    assert app.canvas.cget("background") == NIGHT.page
    assert meowdoku.gui.load_theme(settings) == "night"
    assert meowdoku.gui.load_language(settings) == "ja"  # saving the theme keeps the language
    labels = [app.appearance_menu.entrycget(i, "label") for i in range(3)]
    assert labels == ["自動", "ライト", "ナイト"]


def test_r13_2_auto_follows_the_computer(root: tk.Tk, monkeypatch: pytest.MonkeyPatch) -> None:
    dark = False
    monkeypatch.setattr(meowdoku.gui, "system_is_dark", lambda: dark)
    app = MeowdokuApp(root, GameSession.from_text(EXAMPLE))
    assert app.palette is LIGHT
    dark = True
    app._follow_system()
    assert app.palette is NIGHT
    app.set_theme("light")
    app._follow_system()
    assert app.palette is LIGHT  # a chosen look stays put


def test_r13_4_bad_theme_setting_means_auto(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text('{"theme": "purple"}')
    assert meowdoku.gui.load_theme(settings) == "auto"
