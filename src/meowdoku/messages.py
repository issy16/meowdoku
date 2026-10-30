"""Words the player reads, in English, Traditional Chinese, Japanese, and Korean (R12).

Every sentence is a `Message`: a key into TEXTS plus the details to fill in
(numbers, regions, other messages). A Message is also a `str` holding its
English wording, exactly as before languages were added, so code and tests
that read English keep working (R12.5). `render` words it in any language,
naming regions by color when given their phrases (R12.4, colors.py).

This module imports nothing else from meowdoku, so every module may use it.
"""

import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Union

LANGUAGES: dict[str, str] = {
    "zh-TW": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}
"""Each language's code and its name in that language. Menus put the user's own language first (R12.2)."""

DEFAULT_LANGUAGE = "en"

_COLUMNS = ("en", "zh-TW", "ja", "ko")
"""The order of the languages in every table below, whatever the menu order."""
_INDEX = {code: index for index, code in enumerate(_COLUMNS)}


@dataclass(frozen=True)
class Region:
    """A region named in a message: by color when phrases are given, else by label."""

    label: str


@dataclass(frozen=True)
class Count:
    """A number of things, worded with the right noun: "1 cat", "2 cats", "2 隻貓"."""

    number: int
    noun: str  # a key of NOUNS


Arg = Union[int, str, Region, Count, "Message"]


class Message(str):
    """A sentence to show the player; its `str` value is the English wording."""

    key: str
    args: dict[str, Arg]

    def __new__(cls, key: str, **args: Arg) -> "Message":
        if key not in TEXTS:
            raise KeyError(f"no text for message {key!r}")
        message = super().__new__(cls, _render(key, args, DEFAULT_LANGUAGE, None))
        message.key = key
        message.args = args
        return message


def normalize_language(code: str | None) -> str:
    """A supported language for a code like "ja-JP" or "zh-Hant"; any Chinese is zh-TW (R12.3)."""
    if not code:
        return DEFAULT_LANGUAGE
    lowered = code.lower()
    if lowered.startswith("zh"):
        return "zh-TW"
    for supported in LANGUAGES:
        if lowered.split("-")[0] == supported.lower().split("-")[0]:
            return supported
    return DEFAULT_LANGUAGE


def offered_language(preferred: Sequence[str]) -> str | None:
    """The first of the user's preferred languages that the app offers, or None (R12.3)."""
    for code in preferred:
        language = normalize_language(code)
        if language != DEFAULT_LANGUAGE or code.lower().startswith("en"):
            return language
    return None


def pick_language(preferred: Sequence[str]) -> str:
    """The first of the browser's preferred languages that the app offers, else English (R12.3)."""
    return offered_language(preferred) or DEFAULT_LANGUAGE


def menu_order(preferred: Sequence[str]) -> list[str]:
    """Language codes for a menu: the user's own language first, then the rest as in LANGUAGES (R12.2)."""
    first = offered_language(preferred)
    return ([first] if first else []) + [code for code in LANGUAGES if code != first]


def labels(language: str) -> dict[str, str]:
    """The web page's own wording in `language`: buttons, notices, and the Timings panel, unfilled."""
    return {key: texts[_INDEX[language]] for key, texts in TEXTS.items() if key.startswith(("ui.", "timing."))}


def render(text: str, language: str = DEFAULT_LANGUAGE, regions: Mapping[str, str] | None = None) -> str:
    """Word a message in `language`; plain strings come back unchanged.

    `regions` maps region labels to phrases in that language ("the pink
    region"); without it regions are named by label, as in English errors.
    """
    if not isinstance(text, Message):
        return str(text)
    return _render(text.key, text.args, language, regions)


def label(key: str, language: str = DEFAULT_LANGUAGE, **args: Arg) -> str:
    """A button or other label, worded in `language`."""
    return render(Message(key, **args), language)


class _Formatter(string.Formatter):
    """str.format, plus "{name:lower}" to start a filled-in sentence with a small letter."""

    def format_field(self, value: object, format_spec: str) -> str:
        if format_spec == "lower":
            text = str(value)
            return text[:1].lower() + text[1:]
        return super().format_field(value, format_spec)


_FORMATTER = _Formatter()


def _render(key: str, args: Mapping[str, Arg], language: str, regions: Mapping[str, str] | None) -> str:
    template = TEXTS[key][_INDEX[language]]
    values = {name: _render_arg(value, language, regions) for name, value in args.items()}
    if ":lower" in template:
        return _FORMATTER.format(template, **values)
    return template.format(**values)  # much faster than string.Formatter; D6 makes many messages


def _render_arg(value: Arg, language: str, regions: Mapping[str, str] | None) -> str:
    if isinstance(value, Message):
        return _render(value.key, value.args, language, regions)
    if isinstance(value, Region):
        if regions is not None and value.label in regions:
            return regions[value.label]
        return REGION_BY_LABEL[_INDEX[language]].format(label=repr(value.label))
    if isinstance(value, Count):
        return count_text(value.number, value.noun, language)
    return str(value)


def count_text(number: int, noun: str, language: str = DEFAULT_LANGUAGE) -> str:
    forms = NOUNS[noun][_INDEX[language]]
    if isinstance(forms, tuple):  # English: singular and plural
        return f"{number} {forms[0] if number == 1 else forms[1]}"
    return forms.format(n=number)


REGION_BY_LABEL = ("region {label}", "區域 {label}", "エリア {label}", "영역 {label}")

NOUNS: dict[str, tuple[tuple[str, str] | str, str, str, str]] = {
    "cat": (("cat", "cats"), "{n} 隻貓", "{n}匹", "{n}마리"),
    "step": (("step", "steps"), "{n} 步", "{n}手", "{n}단계"),
    "cell": (("cell", "cells"), "{n} 格", "{n}マス", "{n}칸"),
    "region": (("region", "regions"), "{n} 個區域", "{n}個のエリア", "영역 {n}개"),
}

# Region color names (colors.NAMED_COLORS) and how a region is named by color (R7.8, R12.4)
COLOR_NAMES: dict[str, tuple[str, str, str, str]] = {
    "light green": ("light green", "淺綠色", "ライトグリーン", "연두색"),
    "pink": ("pink", "粉紅色", "ピンク", "분홍색"),
    "brown": ("brown", "咖啡色", "茶色", "갈색"),
    "yellow": ("yellow", "黃色", "黄色", "노란색"),
    "blue": ("blue", "藍色", "青", "파란색"),
    "orange": ("orange", "橘色", "オレンジ", "주황색"),
    "mustard": ("mustard", "芥末黃", "からし色", "겨자색"),
    "purple": ("purple", "紫色", "紫", "보라색"),
    "dark green": ("dark green", "深綠色", "深緑", "진녹색"),
    "rose": ("rose", "玫瑰色", "ローズ", "장미색"),
    "cyan": ("cyan", "青色", "シアン", "시안"),
    "maroon": ("maroon", "栗色", "えび茶色", "적갈색"),
    "lime": ("lime", "萊姆綠", "ライム", "라임색"),
    "red": ("red", "紅色", "赤", "빨간색"),
    "green": ("green", "綠色", "緑", "초록색"),
    "teal": ("teal", "藍綠色", "ティール", "청록색"),
    "gray": ("gray", "灰色", "グレー", "회색"),
    "tan": ("tan", "淺棕色", "黄褐色", "황갈색"),
    "sky blue": ("sky blue", "天藍色", "空色", "하늘색"),
    "coral": ("coral", "珊瑚色", "コーラル", "산호색"),
    "pale blue": ("pale blue", "淺藍色", "水色", "연한 파란색"),
    "beige": ("beige", "米色", "ベージュ", "베이지색"),
    "navy": ("navy", "深藍色", "紺色", "남색"),
    "magenta": ("magenta", "洋紅色", "マゼンタ", "자홍색"),
    "crimson": ("crimson", "深紅色", "深紅", "진홍색"),
    "white": ("white", "白色", "白", "흰색"),
    "black": ("black", "黑色", "黒", "검은색"),
}


def color_region(color: str, language: str, shade: str | None = None) -> str:
    """'the pink region', or with a shade from `shades`, 'the lighter orange region'."""
    name = COLOR_NAMES[color][_INDEX[language]]
    if shade is None:
        return ("the {c} region", "{c}區域", "{c}のエリア", "{c} 영역")[_INDEX[language]].format(c=name)
    template = ("the {s} {c} region", "{s}的{c}區域", "{s}{c}のエリア", "{s} {c} 영역")[_INDEX[language]]
    return template.format(s=shade, c=name)


def shades(count: int, language: str = DEFAULT_LANGUAGE) -> list[str]:
    """Words for `count` shades of one color, lightest first: lighter/darker, or lightest … darkest."""
    index = _INDEX[language]
    if count == 2:
        return [("lighter", "較淺", "明るい方の", "더 밝은")[index], ("darker", "較深", "暗い方の", "더 어두운")[index]]
    english = ["second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
    chinese = "二三四五六七八"
    korean = ["두", "세", "네", "다섯", "여섯", "일곱", "여덟"]
    middle_forms = (
        lambda i: f"{english[i]}-lightest",
        lambda i: f"第{chinese[i]}淺",
        lambda i: f"{i + 2}番目に明るい",
        lambda i: f"{korean[i]} 번째로 밝은",
    )
    lightest = ("lightest", "最淺", "いちばん明るい", "가장 밝은")[index]
    darkest = ("darkest", "最深", "いちばん暗い", "가장 어두운")[index]
    return [lightest, *(middle_forms[index](i) for i in range(count - 2)), darkest]


# Every message in every language: English, 中文 (Traditional, Taiwan), 日本語, 한국어 (R12.5).
# The English wording is the program's original wording; keep it unchanged.
TEXTS: dict[str, tuple[str, str, str, str]] = {
    # D1-D5 (deduce.py)
    "d1": (
        "This cat rules out its row, column, region, and the cells around it.",
        "這隻貓排除了牠所在的列、欄、區域，以及周圍的格子。",
        "この猫と同じ行・列・エリアのマスと、周りのマスには猫を置けません。",
        "이 고양이와 같은 행, 열, 영역의 칸과 주변 칸에는 고양이를 놓을 수 없습니다.",
    ),
    "d2.row": (
        "This row has only 1 cell left.",
        "這一列只剩 1 格。",
        "この行は残り1マスです。",
        "이 행에는 칸이 1개만 남았습니다.",
    ),
    "d2.column": (
        "This column has only 1 cell left.",
        "這一欄只剩 1 格。",
        "この列は残り1マスです。",
        "이 열에는 칸이 1개만 남았습니다.",
    ),
    "d2.region": (
        "This region has only 1 cell left.",
        "這個區域只剩 1 格。",
        "このエリアは残り1マスです。",
        "이 영역에는 칸이 1개만 남았습니다.",
    ),
    "d3.line.row": (  # a region's open cells all lie in this row
        "The cat must be in {region} in this row, so cross out the rest of this row.",
        "{region}的貓一定在這一列，所以把這一列其餘的格子打叉。",
        "{region}の猫はこの行にあるはずなので、この行の残りのマスに✕を付けます。",
        "{region}의 고양이는 이 행에 있어야 하므로, 이 행의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d3.line.column": (
        "The cat must be in {region} in this column, so cross out the rest of this column.",
        "{region}的貓一定在這一欄，所以把這一欄其餘的格子打叉。",
        "{region}の猫はこの列にあるはずなので、この列の残りのマスに✕を付けます。",
        "{region}의 고양이는 이 열에 있어야 하므로, 이 열의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d3.region.row": (  # a row's open cells all lie in this region
        "The cat must be in {region} in this row, so cross out the rest of {region}.",
        "這一列的貓一定在{region}裡，所以把{region}其餘的格子打叉。",
        "この行の猫は{region}にあるはずなので、{region}の残りのマスに✕を付けます。",
        "이 행의 고양이는 {region}에 있어야 하므로, {region}의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d3.region.column": (
        "The cat must be in {region} in this column, so cross out the rest of {region}.",
        "這一欄的貓一定在{region}裡，所以把{region}其餘的格子打叉。",
        "この列の猫は{region}にあるはずなので、{region}の残りのマスに✕を付けます。",
        "이 열의 고양이는 {region}에 있어야 하므로, {region}의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d4.rows": (
        "These regions only fit in these rows, so cross out the rest of those rows.",
        "這些區域只放得進這幾列，所以把這幾列其餘的格子打叉。",
        "これらのエリアはこれらの行にしか収まらないので、これらの行の残りのマスに✕を付けます。",
        "이 영역들은 이 행들 안에만 들어가므로, 이 행들의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d4.columns": (
        "These regions only fit in these columns, so cross out the rest of those columns.",
        "這些區域只放得進這幾欄，所以把這幾欄其餘的格子打叉。",
        "これらのエリアはこれらの列にしか収まらないので、これらの列の残りのマスに✕を付けます。",
        "이 영역들은 이 열들 안에만 들어가므로, 이 열들의 나머지 칸에 ✕를 표시합니다.",
    ),
    "d5": (
        "A cat here would leave {unit} with no room for its cat, so it can't have a cat.",
        "如果這裡有貓，{unit}就沒有位置放貓了，所以這裡不能有貓。",
        "ここに猫がいると{unit}に猫を置く場所がなくなるので、ここには猫を置けません。",
        "여기에 고양이가 있으면 {unit}에 고양이를 놓을 자리가 없으므로, 여기에는 고양이가 없습니다.",
    ),
    # Rows, columns, and regions named without numbers (R7.3)
    "unit.row_above": ("the row above", "上面那一列", "上の行", "위의 행"),
    "unit.row_below": ("the row below", "下面那一列", "下の行", "아래의 행"),
    "unit.row_up": ("a row further up", "更上面的某一列", "もっと上の行", "더 위쪽의 행"),
    "unit.row_down": ("a row further down", "更下面的某一列", "もっと下の行", "더 아래쪽의 행"),
    "unit.column_left": ("the column to the left", "左邊那一欄", "左の列", "왼쪽 열"),
    "unit.column_right": ("the column to the right", "右邊那一欄", "右の列", "오른쪽 열"),
    "unit.column_further_left": ("a column further left", "更左邊的某一欄", "もっと左の列", "더 왼쪽의 열"),
    "unit.column_further_right": ("a column further right", "更右邊的某一欄", "もっと右の列", "더 오른쪽의 열"),
    "unit.this_row": ("this row", "這一列", "この行", "이 행"),
    "unit.this_column": ("this column", "這一欄", "この列", "이 열"),
    "unit.region": ("{region}", "{region}", "{region}", "{region}"),
    # D6 (assume.py)
    "would.empty": (
        "{unit} would have no room for its cat",
        "讓{unit}沒有位置放貓",
        "{unit}に猫を置く場所がなくなる",
        "{unit}에 고양이를 놓을 자리가 없게 됩니다",
    ),
    "would.crowded": (
        "{unit} would have {cats}",
        "讓{unit}有 {cats}",
        "{unit}の猫が{cats}になる",
        "{unit}에 고양이가 {cats} 있게 됩니다",
    ),
    "would.touch": ("2 cats would touch", "讓 2 隻貓相鄰", "2匹の猫が隣り合う", "고양이 2마리가 서로 닿게 됩니다"),
    "breaks.empty": (
        "That leaves {unit} with no room for its cat.",
        "這樣{unit}就沒有位置放貓了。",
        "これで{unit}に猫を置く場所がなくなります。",
        "그러면 {unit}에 고양이를 놓을 자리가 없습니다.",
    ),
    "breaks.crowded": (
        "That puts {cats} in {unit}.",
        "這樣{unit}裡就有 {cats}。",
        "これで{unit}の猫が{cats}になります。",
        "그러면 {unit}에 고양이가 {cats} 있게 됩니다.",
    ),
    "breaks.touch": ("That makes 2 cats touch.", "這樣就有 2 隻貓相鄰。", "これで2匹の猫が隣り合います。", "그러면 고양이 2마리가 서로 닿습니다."),
    "when.now": ("right away", "立刻", "すぐに", "바로"),
    "when.after": ("after {steps}", "{steps}後", "{steps}後に", "{steps} 후에"),
    "d6.cat": (
        "If this cell had a cat, {would} {when}, so it can't have a cat.",
        "如果這格有貓，{when}就會{would}，所以這格不能有貓。",
        "このマスに猫がいると、{when}{would}ので、ここには猫を置けません。",
        "이 칸에 고양이가 있으면 {when} {would}. 따라서 이 칸에는 고양이가 없습니다.",
    ),
    "d6.no_cat": (
        "If this cell had no cat, {would} {when}, so the cat goes here.",
        "如果這格沒有貓，{when}就會{would}，所以貓在這裡。",
        "このマスに猫がいないと、{when}{would}ので、猫はここに入ります。",
        "이 칸에 고양이가 없으면 {when} {would}. 따라서 고양이는 여기에 있습니다.",
    ),
    "d6.look": ("Look at this cell.", "看這一格。", "このマスを見てください。", "이 칸을 보세요."),
    "d6.suppose_cat": ("Suppose it has a cat.", "假設這格有貓。", "ここに猫がいると仮定します。", "여기에 고양이가 있다고 가정해 봅시다."),
    "d6.suppose_no_cat": ("Suppose it has no cat.", "假設這格沒有貓。", "ここに猫がいないと仮定します。", "여기에 고양이가 없다고 가정해 봅시다."),
    "d6.so_no_cat": ("So this cell can't have a cat.", "所以這格不能有貓。", "だから、このマスには猫を置けません。", "따라서 이 칸에는 고양이가 없습니다."),
    "d6.so_cat": ("So the cat goes here.", "所以貓在這裡。", "だから、猫はここに入ります。", "따라서 고양이는 여기에 있습니다."),
    "d6.then": ("Then {reason:lower}", "接著，{reason}", "すると、{reason}", "그러면 {reason}"),
    # Hints (hints.py)
    "hint.no_solution": ("This puzzle has no solution.", "這題沒有解。", "このパズルには解がありません。", "이 퍼즐에는 답이 없습니다."),
    "hint.solved": ("The puzzle is solved!", "題目解開了！", "パズルが解けました！", "퍼즐을 풀었습니다!"),
    "hint.no_step": (
        "No simple step found; try Solve.",
        "找不到簡單的下一步，試試「解答」。",
        "簡単な次の一手が見つかりません。「解答」を試してください。",
        "간단한 다음 단계를 찾지 못했습니다. '정답'을 눌러 보세요.",
    ),
    "hint.touch": ("These cats touch.", "這些貓相鄰了。", "これらの猫は隣り合っています。", "이 고양이들이 서로 닿아 있습니다."),
    "hint.off_board": ("This cat is off the board.", "這隻貓在棋盤外。", "この猫は盤の外にいます。", "이 고양이는 판 밖에 있습니다."),
    "hint.crowded.row": ("This row has {n} cats.", "這一列有 {n} 隻貓。", "この行に猫が{n}匹います。", "이 행에 고양이가 {n}마리 있습니다."),
    "hint.crowded.column": ("This column has {n} cats.", "這一欄有 {n} 隻貓。", "この列に猫が{n}匹います。", "이 열에 고양이가 {n}마리 있습니다."),
    "hint.crowded.region": ("This region has {n} cats.", "這個區域有 {n} 隻貓。", "このエリアに猫が{n}匹います。", "이 영역에 고양이가 {n}마리 있습니다."),
    "hint.wrong_mark": ("This mark is wrong.", "這個標記是錯的。", "この印は間違っています。", "이 표시는 틀렸습니다."),
    "hint.some_wrong": ("Some of your marks are wrong.", "你有些標記是錯的。", "いくつかの印が間違っています。", "일부 표시가 틀렸습니다."),
    # The game (game.py)
    "game.step": ("Step {number}: {text}", "第 {number} 步：{text}", "ステップ{number}：{text}", "{number}단계: {text}"),
    # Cells, 1-indexed (R6.4)
    "cell": ("row {row}, column {column}", "第 {row} 列第 {column} 欄", "{row}行{column}列", "{row}행 {column}열"),
    # Errors players can meet when opening a screenshot (image_import.py, puzzle.py)
    "err.not_screenshot": (
        "{name} is not a screenshot; use a .png, .jpg, or .jpeg file",
        "{name} 不是截圖；請使用 .png、.jpg 或 .jpeg 檔案",
        "{name} はスクリーンショットではありません。.png、.jpg、.jpeg のファイルを使ってください",
        "{name} 파일은 스크린샷이 아닙니다. .png, .jpg, .jpeg 파일을 사용하세요",
    ),
    "err.unreadable": (
        "{name} is not a readable PNG or JPEG image",
        "{name} 不是可讀取的 PNG 或 JPEG 圖片",
        "{name} は読み込める PNG か JPEG の画像ではありません",
        "{name} 파일은 읽을 수 있는 PNG 또는 JPEG 이미지가 아닙니다",
    ),
    "err.no_tiles": (
        "couldn't find the board: no colored tiles were found",
        "找不到棋盤：沒有找到彩色方格",
        "盤面が見つかりません：色付きのマスがありません",
        "판을 찾지 못했습니다: 색칠된 칸이 없습니다",
    ),
    "err.no_grid": (
        "couldn't find the board: no square grid of colored tiles was found",
        "找不到棋盤：沒有找到由彩色方格組成的正方形格子",
        "盤面が見つかりません：色付きのマスが正方形に並んでいません",
        "판을 찾지 못했습니다: 색칠된 칸으로 된 정사각형 격자가 없습니다",
    ),
    "err.not_square": (
        "found a grid {across} cells wide and {down} cells tall; the board must be square",
        "找到寬 {across} 格、高 {down} 格的格子；棋盤必須是正方形",
        "横{across}マス、縦{down}マスの盤面が見つかりました。盤面は正方形でなければなりません",
        "가로 {across}칸, 세로 {down}칸의 격자를 찾았습니다. 판은 정사각형이어야 합니다",
    ),
    "err.size": (
        "found {across} cells per row; boards must have 1 to {max}",
        "每列找到 {across} 格；棋盤必須是 1 到 {max} 格",
        "1行に{across}マス見つかりました。盤面は1〜{max}マスでなければなりません",
        "한 행에 {across}칸을 찾았습니다. 판은 1~{max}칸이어야 합니다",
    ),
    "err.tile_color": (
        "couldn't read a tile's color: it is all white or black",
        "無法讀取方格的顏色：整格都是白色或黑色",
        "マスの色を読み取れません：真っ白か真っ黒です",
        "칸의 색을 읽을 수 없습니다: 전부 흰색이거나 검은색입니다",
    ),
    "err.region_colors": (
        "found {found} region colors; expected {expected}",
        "找到 {found} 種區域顏色；應該是 {expected} 種",
        "エリアの色が{found}色見つかりました。{expected}色のはずです",
        "영역 색을 {found}가지 찾았습니다. {expected}가지여야 합니다",
    ),
    "err.cannot_read": (
        "cannot read {name}: {reason}",
        "無法讀取 {name}：{reason}",
        "{name} を読み込めません：{reason}",
        "{name} 파일을 읽을 수 없습니다: {reason}",
    ),
    "err.save_unreadable": (
        "Your saved game couldn't be opened, so a new game was started.",
        "無法開啟你儲存的遊戲，所以開始了新的一局。",
        "保存したゲームを開けなかったので、新しいゲームを始めました。",
        "저장된 게임을 열 수 없어서 새 게임을 시작했습니다.",
    ),
    "ui.save_failed": (
        "Couldn't save your game on this device.",
        "無法在這台裝置上儲存你的遊戲。",
        "このデバイスにゲームを保存できませんでした。",
        "이 기기에 게임을 저장하지 못했습니다.",
    ),
    # Signing in and the game kept in the player's account, web only (R11.6–R11.11)
    "ui.sign_in_google": ("Sign in with Google", "使用 Google 登入", "Google でログイン", "Google로 로그인"),
    "ui.sign_in_email": ("Sign in with email", "使用電子郵件登入", "メールでログイン", "이메일로 로그인"),
    "ui.email": ("Your email", "你的電子郵件", "メールアドレス", "이메일 주소"),
    "ui.send_link": ("Send link", "寄送連結", "リンクを送信", "링크 보내기"),
    "ui.link_sent": (
        "Check your email for a sign-in link, and open it on this device.",
        "請到信箱查看登入連結，並在這台裝置上開啟。",
        "ログイン用のリンクをメールで送りました。このデバイスで開いてください。",
        "이메일로 로그인 링크를 보냈습니다. 이 기기에서 열어 주세요.",
    ),
    "ui.signed_in_as": ("Signed in as {name}", "已登入：{name}", "ログイン中：{name}", "로그인됨: {name}"),
    "ui.sign_out": ("Sign out", "登出", "ログアウト", "로그아웃"),
    "ui.delete_account": ("Delete account", "刪除帳號", "アカウントを削除", "계정 삭제"),
    "ui.delete_confirm": (
        "Delete your account and the game saved in it? This can't be undone. Your game stays on this device.",
        "要刪除你的帳號和裡面儲存的遊戲嗎？刪除後無法復原。這台裝置上的遊戲會保留。",
        "アカウントと保存したゲームを削除しますか？元に戻せません。このデバイスのゲームは残ります。",
        "계정과 저장된 게임을 삭제할까요? 되돌릴 수 없습니다. 이 기기의 게임은 남아 있습니다.",
    ),
    "ui.account_deleted": (
        "Your account and its saved game were deleted.",
        "已刪除你的帳號和儲存的遊戲。",
        "アカウントと保存したゲームを削除しました。",
        "계정과 저장된 게임을 삭제했습니다.",
    ),
    "ui.account_save_failed": (
        "Couldn't save your game to your account. It's still saved on this device.",
        "無法把遊戲儲存到你的帳號，但它仍儲存在這台裝置上。",
        "アカウントにゲームを保存できませんでした。このデバイスには保存されています。",
        "계정에 게임을 저장하지 못했습니다. 이 기기에는 저장되어 있습니다.",
    ),
    "ui.account_load_failed": (
        "Couldn't load the game saved in your account.",
        "無法載入你帳號裡儲存的遊戲。",
        "アカウントに保存したゲームを読み込めませんでした。",
        "계정에 저장된 게임을 불러오지 못했습니다.",
    ),
    "ui.account_restored": (
        "Picked up the game saved in your account.",
        "已載入你帳號裡儲存的遊戲。",
        "アカウントに保存したゲームを読み込みました。",
        "계정에 저장된 게임을 불러왔습니다.",
    ),
    "ui.sign_in_failed": (
        "Couldn't sign in: {reason}",
        "無法登入：{reason}",
        "ログインできませんでした：{reason}",
        "로그인하지 못했습니다: {reason}",
    ),
    "ui.account_error": (
        "Something went wrong with your account: {reason}",
        "帳號發生錯誤：{reason}",
        "アカウントでエラーが発生しました：{reason}",
        "계정에 문제가 발생했습니다: {reason}",
    ),
    "err.invalid": ("invalid puzzle:", "題目無效：", "無効なパズルです：", "잘못된 퍼즐입니다:"),
    "err.board_size": (
        "board size {size} is not supported; it must be between {min} and {max}",
        "不支援大小為 {size} 的棋盤；大小必須在 {min} 到 {max} 之間",
        "盤面のサイズ {size} には対応していません。{min}〜{max} でなければなりません",
        "판 크기 {size}은(는) 지원하지 않습니다. {min}~{max} 사이여야 합니다",
    ),
    "err.region_count": (
        "found {regions} ({labels}); a {size}x{size} board needs exactly {size}",
        "找到 {regions}（{labels}）；{size}x{size} 的棋盤需要剛好 {size} 個",
        "{regions}（{labels}）が見つかりました。{size}x{size} の盤面にはちょうど{size}個必要です",
        "{regions}({labels})를 찾았습니다. {size}x{size} 판에는 정확히 {size}개가 필요합니다",
    ),
    "err.split": (
        "{region} is split into {parts} separate parts (starting at {starts}); "
        "every region must be one connected area",
        "{region}被分成 {parts} 塊（從 {starts} 開始）；每個區域都必須連成一塊",
        "{region}が{parts}つに分かれています（{starts} から）。どのエリアもひとつながりでなければなりません",
        "{region}이(가) {parts}개로 나뉘어 있습니다({starts}부터). 모든 영역은 하나로 이어져야 합니다",
    ),
    "err.and": ("{first} and {second}", "{first}和{second}", "{first}と{second}", "{first}, {second}"),
    # Buttons and other labels, desktop and web (R12.1)
    "ui.title": ("Meowdoku", "Meowdoku", "Meowdoku", "Meowdoku"),
    "ui.open": ("Open", "開啟", "開く", "열기"),
    "ui.open_dialog": ("Open…", "開啟…", "開く…", "열기…"),
    "ui.previous": ("Previous", "復原", "元に戻す", "되돌리기"),
    "ui.next": ("Next", "重做", "やり直す", "다시 하기"),
    "ui.hint": ("Hint", "提示", "ヒント", "힌트"),
    "ui.step": ("Step by Step", "逐步解題", "ステップごと", "단계별"),
    "ui.next_step": ("Next Step", "下一步", "次のステップ", "다음 단계"),
    "ui.solve": ("Solve", "解答", "解答", "정답"),
    "ui.reset": ("Reset", "重來", "リセット", "초기화"),
    "ui.apply": ("Apply?", "套用？", "適用する？", "적용할까요?"),
    "ui.show_me": ("Show me", "示範給我看", "見せて", "보여 주기"),
    "ui.solved_title": ("Puzzle solved!", "解開了！", "クリア！", "퍼즐 완성!"),
    "ui.solved_subtitle": ("Well done!", "做得好！", "よくできました！", "잘했어요!"),
    "ui.ok": ("OK", "好", "OK", "확인"),
    "ui.walk_title": ("What if?", "如果呢？", "もしも？", "만약에?"),
    "ui.walk_count": ("Step {number} of {total}", "第 {number} 步，共 {total} 步", "ステップ {number}/{total}", "{number}/{total}단계"),
    "ui.back": ("Back", "上一步", "戻る", "이전"),
    "ui.walk_next": ("Next", "下一步", "次へ", "다음"),
    "ui.done": ("Done", "完成", "完了", "완료"),
    "ui.close": ("Close", "關閉", "閉じる", "닫기"),
    "ui.open_title": ("Open a screenshot", "開啟截圖", "スクリーンショットを開く", "스크린샷 열기"),
    "ui.screenshots": ("Screenshots", "截圖", "スクリーンショット", "스크린샷"),
    "ui.all_files": ("All files", "所有檔案", "すべてのファイル", "모든 파일"),
    "ui.cant_open": ("Can't open puzzle", "無法開啟題目", "パズルを開けません", "퍼즐을 열 수 없습니다"),
    "ui.went_wrong": ("Something went wrong", "發生錯誤", "エラーが発生しました", "문제가 발생했습니다"),
    "ui.went_wrong_reason": (
        "Something went wrong: {reason}",
        "發生錯誤：{reason}",
        "エラーが発生しました：{reason}",
        "문제가 발생했습니다: {reason}",
    ),
    "ui.example_instead": (
        "Showing the example puzzle instead.",
        "改為顯示範例題目。",
        "代わりに例題を表示します。",
        "대신 예제 퍼즐을 표시합니다.",
    ),
    "ui.language": ("Language", "語言", "言語", "언어"),
    "ui.appearance": ("Appearance", "外觀", "表示モード", "화면 모드"),
    "ui.appearance_choice": ("Appearance: {choice}", "外觀：{choice}", "表示モード：{choice}", "화면 모드: {choice}"),
    "ui.theme_auto": ("Auto", "自動", "自動", "자동"),
    "ui.theme_light": ("Light", "淺色", "ライト", "라이트"),
    "ui.theme_night": ("Night", "夜間", "ナイト", "야간"),
    "ui.loading": ("Loading…", "載入中…", "読み込み中…", "불러오는 중…"),
    "ui.load_failed": (
        "Couldn't load the game: {reason}",
        "無法載入遊戲：{reason}",
        "ゲームを読み込めませんでした：{reason}",
        "게임을 불러오지 못했습니다: {reason}",
    ),
    "ui.pick_png": (
        "Please choose a PNG or JPEG screenshot.",
        "請選擇 PNG 或 JPEG 截圖。",
        "PNG か JPEG のスクリーンショットを選んでください。",
        "PNG 또는 JPEG 스크린샷을 선택하세요.",
    ),
    "ui.too_big_bytes": ("That file is over 20 MB.", "這個檔案超過 20 MB。", "このファイルは 20 MB を超えています。", "이 파일은 20MB를 넘습니다."),
    "ui.too_big_pixels": (
        "That image is over {max} pixels wide or tall.",
        "這張圖片的寬或高超過 {max} 像素。",
        "この画像は幅か高さが {max} ピクセルを超えています。",
        "이 이미지는 가로 또는 세로가 {max}픽셀을 넘습니다.",
    ),
    "ui.not_image": (
        "That file isn't an image this browser can read.",
        "這個瀏覽器無法讀取這個檔案。",
        "このブラウザーでは読み込めない画像です。",
        "이 브라우저에서 읽을 수 없는 이미지입니다.",
    ),
    # The web app's Timings panel (R11.12)
    "ui.timings": ("Timings", "耗時", "所要時間", "소요 시간"),
    "ui.timings_note": (
        "How long each step took in this browser (R11.12).",
        "每個步驟在這個瀏覽器中花了多少時間（R11.12）。",
        "このブラウザーで各ステップにかかった時間（R11.12）。",
        "이 브라우저에서 각 단계에 걸린 시간 (R11.12).",
    ),
    "ui.sample": ("Open sample screenshot", "開啟範例截圖", "サンプルのスクリーンショットを開く", "샘플 스크린샷 열기"),
    "ui.measure": ("Measure hints and Solve", "測量提示與解答", "ヒントと解答を計測", "힌트와 정답 측정"),
    "ui.last_action": ("Last action", "上一個動作", "直前の操作", "마지막 동작"),
    "timing.start": ("Start Python", "啟動 Python", "Python の起動", "Python 시작"),
    "timing.pillow": ("Load Pillow", "載入 Pillow", "Pillow の読み込み", "Pillow 불러오기"),
    "timing.package": ("Load meowdoku", "載入 meowdoku", "meowdoku の読み込み", "meowdoku 불러오기"),
    "timing.import": ("Screenshot import", "匯入截圖", "スクリーンショットの読み込み", "스크린샷 가져오기"),
    "timing.solve": ("Solve (first time)", "解答（第一次）", "解答（初回）", "정답 (처음)"),
    "timing.first_hint": ("First hint", "第一個提示", "最初のヒント", "첫 힌트"),
    "timing.slowest": ("Slowest of {n} hints", "{n} 個提示中最慢的", "{n}個のヒントで最も遅いもの", "힌트 {n}개 중 가장 느린 것"),
    "timing.all_hints": ("All hints to solve", "解完所需的全部提示", "解くまでの全ヒント", "풀 때까지의 모든 힌트"),
    "timing.slowest_d6": ("Slowest D6 hint", "最慢的 D6 提示", "最も遅い D6 ヒント", "가장 느린 D6 힌트"),
    "timing.none_needed": ("none needed", "不需要", "不要", "필요 없음"),
    "timing.solved_by_hints": ("Solved by hints alone", "只靠提示解完", "ヒントだけで解けた", "힌트만으로 풀림"),
    "timing.yes": ("yes", "是", "はい", "예"),
    "timing.no": ("no", "否", "いいえ", "아니요"),
    # The command line (cli.py, R6)
    "cli.description": (
        "Solve a Meowdoku puzzle and report whether it has none, one, or several solutions.",
        "解 Meowdoku 題目，並回報它沒有解、只有一個解，還是有多個解。",
        "Meowdoku のパズルを解き、解がない・ひとつ・複数のどれかを表示します。",
        "Meowdoku 퍼즐을 풀고 해답이 없는지, 하나인지, 여러 개인지 알려 줍니다.",
    ),
    "cli.screenshot_help": (
        "a .png or .jpg screenshot of the board",
        "棋盤的 .png 或 .jpg 截圖",
        "盤面の .png か .jpg のスクリーンショット",
        "판의 .png 또는 .jpg 스크린샷",
    ),
    "cli.count_all_help": (
        "count every solution instead of stopping at two (may be slow)",
        "計算所有的解，而不是找到兩個就停（可能很慢）",
        "2つで止めずにすべての解を数えます（遅いことがあります）",
        "두 개에서 멈추지 않고 모든 해답을 셉니다 (느릴 수 있음)",
    ),
    "cli.language_help": (
        "language for the output: en, zh-TW, ja, or ko",
        "輸出的語言：en、zh-TW、ja 或 ko",
        "出力の言語：en、zh-TW、ja、ko",
        "출력 언어: en, zh-TW, ja, ko",
    ),
    "cli.error": ("meowdoku: error: {message}", "meowdoku：錯誤：{message}", "meowdoku: エラー: {message}", "meowdoku: 오류: {message}"),
    "cli.detected": ("Detected puzzle:", "偵測到的題目：", "読み取ったパズル：", "인식한 퍼즐:"),
    "cli.marks": (
        "Detected marks (* cat, x cross):",
        "偵測到的標記（* 貓，x 叉）：",
        "読み取った印（* 猫、x バツ）：",
        "인식한 표시 (* 고양이, x 엑스):",
    ),
    "cli.solutions": ("Solutions: {n}", "解的數量：{n}", "解の数：{n}", "해답 수: {n}"),
    "cli.showing": (
        "Showing the first {n} solutions.",
        "顯示前 {n} 個解。",
        "最初の{n}個の解を表示します。",
        "처음 {n}개의 해답을 표시합니다.",
    ),
    "cli.solution": ("Solution {n}:", "解 {n}：", "解 {n}：", "해답 {n}:"),
    "cli.cats": ("{cats}: {positions}", "{cats}：{positions}", "猫{cats}：{positions}", "고양이 {cats}: {positions}"),
    "cli.separator": ("; ", "；", "、", "; "),
}
