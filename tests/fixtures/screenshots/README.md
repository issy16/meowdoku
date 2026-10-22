# Real screenshots for import tests (R9.5)

Put Meowdoku screenshots here, each with a text file of the same name that
holds the expected grid:

```text
board-7x7.png
board-7x7.txt      one line per row, one letter per region, e.g. AABBB
```

Any letters work in the `.txt` file; regions are matched by shape, not by
letter. `tests/test_image_import.py` picks up every `.png`/`.jpg`/`.jpeg`
here automatically. Include at least one board with cats and ✕ marks.
