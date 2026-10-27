"""Messages in English, Traditional Chinese, Japanese, and Korean (R12)."""

import re
import string
from pathlib import Path

import pytest

from meowdoku.colors import NAMED_COLORS, region_phrases
from meowdoku.game import GameSession
from meowdoku.messages import (
    COLOR_NAMES,
    LANGUAGES,
    NOUNS,
    TEXTS,
    Count,
    Message,
    Region,
    count_text,
    normalize_language,
    pick_language,
    render,
    shades,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_r12_5_every_message_has_every_language() -> None:
    for key, texts in TEXTS.items():
        assert len(texts) == len(LANGUAGES), key
        assert all(text.strip() for text in texts), key


def test_r12_5_every_language_fills_in_the_same_details() -> None:
    for key, texts in TEXTS.items():
        assert {frozenset(fields(text)) for text in texts} == {frozenset(fields(texts[0]))}, key


def test_r12_4_every_color_name_is_translated() -> None:
    assert {name for name, _ in NAMED_COLORS} == set(COLOR_NAMES)
    assert all(len(names) == len(LANGUAGES) for names in COLOR_NAMES.values())
    assert all(len(forms) == len(LANGUAGES) for forms in NOUNS.values())


def test_r12_5_a_message_is_its_english_wording() -> None:
    message = Message("d2.row")
    assert message == "This row has only 1 cell left."
    assert render(message, "ja") == "この行は残り1マスです。"
    assert render("plain text", "ko") == "plain text"
    with pytest.raises(KeyError):
        Message("no such message")


def test_r12_4_nested_messages_are_worded_together() -> None:
    then = Message("d6.then", reason=Message("d2.row"))
    assert then == "Then this row has only 1 cell left."
    assert render(then, "zh-TW") == "接著，這一列只剩 1 格。"


def test_r12_4_regions_are_named_by_color_when_phrases_are_given() -> None:
    message = Message("d5", unit=Message("unit.region", region=Region("A")))
    assert "region 'A'" in message  # the English wording names the label
    assert render(message, "ko", {"A": "분홍색 영역"}).startswith("여기에 고양이가 있으면 분홍색 영역에")
    assert render(message, "ja") .startswith("ここに猫がいるとエリア 'A'に")


def test_count_words_the_noun() -> None:
    assert count_text(1, "cat") == "1 cat"
    assert count_text(2, "cat") == "2 cats"
    assert count_text(2, "cat", "zh-TW") == "2 隻貓"
    assert render(Message("breaks.crowded", unit=Message("unit.this_row"), cats=Count(2, "cat")), "ko") == (
        "그러면 이 행에 고양이가 2마리 있게 됩니다."
    )


@pytest.mark.parametrize("language", list(LANGUAGES))
def test_r7_8_shades_tell_regions_apart_in_every_language(language: str) -> None:
    colors = {"A": "#eda068", "B": "#f7c19b", "C": "#9dd387"}  # two oranges and a green
    phrases = region_phrases(colors, language)
    assert len(set(phrases.values())) == 3
    assert len(shades(5, language)) == len(set(shades(5, language))) == 5


def test_r7_8_english_region_phrases_are_unchanged() -> None:
    phrases = region_phrases({"A": "#eda068", "B": "#f7c19b"})
    assert phrases == {"A": "the darker orange region", "B": "the lighter orange region"}


@pytest.mark.parametrize(
    ("code", "expected"),
    [("en-US", "en"), ("zh-Hant-TW", "zh-TW"), ("zh-CN", "zh-TW"), ("ja-JP", "ja"), ("ko", "ko"), ("fr", "en"), (None, "en")],
)
def test_r12_3_normalize_language(code: str | None, expected: str) -> None:
    assert normalize_language(code) == expected


def test_r12_3_pick_language_takes_the_first_offered() -> None:
    assert pick_language(["fr-FR", "de", "ja-JP", "ko"]) == "ja"
    assert pick_language(["en-GB", "ja"]) == "en"
    assert pick_language(["fr"]) == "en"


@pytest.mark.parametrize("language", ["zh-TW", "ja", "ko"])
def test_r12_4_hints_and_steps_never_show_letters_or_english(language: str) -> None:
    """R7.3 and R7.8 in every language: a whole game of hints, Step by Step, and Show me."""
    session = GameSession.from_screenshot(FIXTURES / "screenshots" / "IMG_7117.PNG", language)
    seen = []
    session.step()
    for _ in range(80):
        seen.append(session.message)
        if session.can_show_me:
            session.show_me()
            while session.walking:
                seen.append(session.caption)
                session.next_frame()
        if not session.stepping:
            break
        session.step()
    assert len(seen) > 10
    for text in seen:
        assert "'" not in text, text  # no region letters like region 'A'
        assert not re.search(r"[A-Za-z]{3,}", text), text  # no English left over


def test_r12_1_chinese_comes_first_and_is_named_chinese() -> None:
    assert list(LANGUAGES.items())[0] == ("zh-TW", "中文")
    assert render(Message("ui.hint"), "zh-TW") == "提示"  # the tables keep their own column order
