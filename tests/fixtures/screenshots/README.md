# Real screenshots for import tests (R9.5, R9.6)

`IMG_*` files are screenshots of the Meowdoku game. `gui-*` files are
screenshots of this program's own window, with their `.txt` and `.marks`
files, made by `python tests/capture_window_screenshots.py`; remake them
when the window's look changes.

Put Meowdoku screenshots here, each with a text file of the same name that
holds the expected grid:

```text
board-7x7.png
board-7x7.txt      one line per row, one letter per region, e.g. AABBB
```

Any letters work in the `.txt` file; regions are matched by shape, not by
letter. Lines starting with `#` are comments.

If the board shows cats or ✕ marks, add a `.marks` file of the same name: one
line per row, `*` for a cat, `x` for a ✕, `.` for an empty tile. Without a
`.marks` file, the board is expected to be empty. `tests/test_image_import.py` picks up every `.png`/`.jpg`/`.jpeg`
here automatically. Include at least one board with cats and ✕ marks.
