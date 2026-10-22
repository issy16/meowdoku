# Algorithm Design

## Problem as a constraint satisfaction problem

Because every row holds exactly one cat (R1.1), a solution is fully described
by one value per row:

- **Variables:** `col[r]` for each row `r` in `0..N-1`
- **Domain:** `0..N-1` (the column of the cat in row `r`)
- **Constraints:**
  - Columns: all `col[r]` are distinct (R1.2)
  - Regions: the regions `region(r, col[r])` are all distinct (R1.3)
  - Adjacency: `|col[r] - col[r+1]| > 1` for consecutive rows (R1.4)

The row rule needs no check because this representation can only place one cat
per row. The adjacency rule only involves consecutive rows: two cats in the
same row can't exist, and rows two or more apart can't touch.

## Search: row-by-row backtracking

```text
search(row):
    if row == N: yield the current placement; return
    for col in 0..N-1:
        if col is used:                          skip
        if region(row, col) is used:             skip
        if row > 0 and |col - col[row-1]| <= 1:  skip
        place cat at (row, col); mark column and region used
        search(row + 1)
        remove cat; unmark column and region
```

- `iter_solutions(puzzle)` is a generator built on this search. It yields
  solutions in lexicographic order (R2.4).
- `solve(puzzle, max_solutions=2)` takes solutions from the generator until
  it reaches `max_solutions` or runs out, then classifies the result:
  0 → `NONE`, 1 → `UNIQUE`, 2 or more → `MULTIPLE`.
- Each check uses a set lookup or one comparison, so it runs in constant time.

### Why stop at two solutions

Telling `UNIQUE` apart from `MULTIPLE` only requires knowing whether a second
solution exists. Stopping there avoids enumerating every solution of a puzzle
that has many. `max_solutions=None` turns off the limit for counting and for
tests.

### Complexity

In the worst case the search tries all N! column orderings, but the column,
region, and adjacency checks prune most branches early. Hand-designed puzzles
with N ≤ 12 are expected to solve in well under a second.

## Optimization: region dead-end pruning

After placing a cat, abandon the branch if some region without a cat has no
open cell left. A cell is open if it's in a later row, in an unused column,
and not touching the cat just placed. Without this check, the search only
discovers an empty region when it reaches that region's last row.

Measured on 30 random 12×12 puzzles (seeded), before → after:

| | Median | Worst | Over 1 s |
|---|---|---|---|
| Plain backtracking | 0.241 s | 10.1 s | 6 / 30 |
| With pruning | 0.003 s | 1.27 s | 1 / 30 |

All oracle tests pass unchanged. Over 300 random 12×12 puzzles, 2 still take
more than 1 second (worst 3.2 s). Both had no solution or several; random
puzzles almost never have a unique solution, unlike real game puzzles.

## Separation from validation

`rules.find_violations` checks a finished placement directly against R1.1–R1.4
on a plain set of cells. It shares no code with the solver beyond the `Puzzle`
type. It is the reference that solver output is tested against.

## Testing oracles

The solver is never tested only against itself:

1. **Rule validator:** every solution the solver returns must have zero violations.
2. **Brute-force enumeration:** for N ≤ 6, generate every permutation with
   `itertools.permutations` and filter with the validator. The resulting
   solution set must equal `solve(p, max_solutions=None)` on ~200 random
   region maps generated with fixed seeds.
3. **OEIS A002464 (Hertzsprung's problem):** when each row is its own region,
   the region rule adds nothing, so the solution count must equal the number of
   permutations with no two neighbors differing by 1:

   | N | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
   |---|---|---|---|---|---|---|---|---|
   | count | 1 | 0 | 0 | 2 | 14 | 90 | 646 | 5242 |

4. **Metamorphic transforms:** rotating, reflecting, or transposing a puzzle,
   or renaming its regions, must keep the solution count the same and transform
   each solution the same way.
5. **Hand-verified fixtures:** puzzles with known answers in `tests/fixtures/`.

## Hints: deduction rules

Hints reason over a `BoardState` where each cell is a cat, ✕, or open
(neither). `next_hint` works in this order and stops at the first result:

1. **No solution:** if the puzzle itself has no solution, say so (R7.6).
   **Solved:** if the placed cats are a complete valid solution, say so.
2. **Rule violations:** use `rules.find_conflicts` on the placed cats. It
   reports too many cats and touching cats, but not rows, columns, or regions
   that simply don't have a cat yet.
3. **Mistakes:** if no solution matches the current marks, report it (R7.5).
4. **Deduction rules D1–D5** below, simplest first.
5. **Nothing found:** "No simple step found; try Solve." Hints never reveal
   the solution (R7.6).

| Rule | Name | Statement |
|---|---|---|
| D1 | Cat neighborhood | A placed cat rules out every other cell in its row, column, and region, plus its 8 neighbors |
| D2 | Last open cell | A row, column, or region with no cat and exactly one open cell must have its cat there |
| D3 | Confinement | If a region's open cells all lie in one row, the other cells in that row are ✕ (same for columns). Reverse: if a row's open cells all lie in one region, the region's other cells are ✕ |
| D4 | Pigeonhole | If k regions have all their open cells inside the same k rows, every other cell in those rows is ✕ (same for columns). D3 is the case k = 1 |
| D5 | Blocking | An open cell is ✕ if a cat there would rule out every open cell of some other row, column, or region |

- D3–D5 only consider rows, columns, and regions that have no cat yet. For a
  unit with no open cells left, "all its open cells" would be vacuously true.
- Rules are checked in this fixed order, and cells are scanned in row-major
  order, so hints are deterministic (R7.4).
- D4 checks groups of regions up to size N/2. That's at most a few thousand
  groups for N ≤ 16, which is fast enough and easy to read.

### Module boundaries

- `deduce.py` implements D1–D5 using only `Puzzle` and `BoardState`. It
  never imports `solver.py`.
- `hints.py` combines the steps above. It's the only place where deduction,
  rule checking, and solving meet.
- Mistake detection (step 2) takes solutions from `iter_solutions` and stops
  at the first one that matches the marks.

### Testing hints

- **Per-rule tests:** small hand-built states where exactly one rule applies.
- **Soundness (R7.7):** for unique puzzles from the fixtures and seeded
  random generation, apply hints repeatedly from an empty board. Every
  placed cat and every ✕ must agree with the solution, checked by the
  validator. A disagreement means a rule is unsound.
- **Progress:** in tests (the GUI never applies hints), applying a hint's
  conclusion must add at least one new mark. Repeating this ends with the
  puzzle solved or with "No simple step found". Tests record which fixtures
  D1–D5 solve completely.
- **Mistakes:** one wrong mark on an otherwise correct board must produce a
  mistake hint pointing at that mark, never a deduction built on it.
- **Mutation check:** deliberately weakening D5 makes 24 soundness tests
  fail, so the tests do catch unsound rules.

Measured at Milestone 6: hints alone fully solve the README example and all
30 seeded random 5×5–8×8 puzzles with a unique solution. `next_hint` takes
about 0.01 s on 10×10–12×12 boards.

## Screenshot import

`image_import.py` turns a screenshot into the text grid in four steps. Each
step is a separate function, so tuning one doesn't disturb the others.

The real game draws the board as a white rounded card of **rounded colored
tiles with white gaps** between them, on a beige page. There are no grid
lines and no region borders: regions are shown only by tile color.
(Measured on `tests/fixtures/screenshots/IMG_7128.jpg`: 105 px tiles,
9 px gaps, about 8 px corner radius.)

1. **Find the board (`find_board`).** Read the page color from the image
   corners. Tile pixels are those that differ by more than 40 in some color
   channel from both white and the page color. Rows where at least 30% of the
   pixels are tile pixels form horizontal bands; gaps of up to 2% of the image
   width (the white gaps between tile rows) are bridged. Headers, icons,
   buttons, and ad banners make short, wide bands. The board is the largest
   band whose colored area is square. This works on full, uncropped phone
   screenshots.
2. **Count the cells (`count_cells`).** Read pixel colors straight across
   the board along 60 rows and 60 columns. At each position, ask whether the
   color changes sharply within a few pixels, and take the median answer.
   The white gaps cross every row and column, so they survive the median;
   cats and ✕ marks cross only some, so they don't. The median spacing gives
   N, which must agree in both directions.
3. **Read cell colors (`cell_color`).** Sample a band 15–20% inside each
   cell's edges, clear of the gaps, the rounded corners, and the icons in the
   middle. Take the most common color there. This is how cats and ✕ marks are
   ignored (R9.1a).
4. **Group colors into regions (`group_colors`).** Join cells whose colors
   are within RGB distance 28, in chains. The real game's 10 colors are at
   least 64 apart. There must be exactly N groups, otherwise raise
   `ImageImportError` ("found 6 region colors; expected 7"). Label groups
   `A`, `B`, … in row-major order of first appearance, then pass the text
   grid to the normal parser, which validates it (R4).

**History.** The first version (Milestone 8) guessed at a board with a dark
frame, grid lines, and thick region borders. The real screenshot has none of
those, so step 1 was replaced. It first took the box around *all* tile pixels,
which needed a cropped screenshot. Banding the rows, added for
`IMG_7114.PNG`, made full screenshots work. Steps 2–4 carried over: the white gaps act
like grid lines for step 2. Two earlier fixes still matter:

- Gaps are found by *color change*, not brightness.
- Colors are sampled near the cell *edges*, because an icon covers most of a
  cell's middle.

**Status.**

- **Real screenshots:** both read correctly.
  - `IMG_7128.jpg`: a cropped 10×10 empty board.
  - `IMG_7114.PNG`: a full 1206×2622 phone screenshot of another 10×10
    empty board, with the header, rule card, buttons, and an ad banner.

  Both expected grids were transcribed by Claude and still need the owner's
  confirmation. Each has exactly one solution, which a misread cell would
  very likely break. Copies of both also read correctly when shrunk to a third
  of their size or saved as JPEG quality 40. Each takes about 0.5 s.
- **Synthetic screenshots:** drawn in the measured style, from 4×4 to 12×12,
  as PNG and JPEG, with and without cats and ✕ marks, both cropped and inside
  a full phone screen.

**Known limits:**

- How the real game draws cats and ✕ marks hasn't been seen yet. The tests
  use dark marks in the middle of the tile.
- Dark mode hasn't been seen either.
- A square, colorful ad could be mistaken for the board if it is larger
  than the board. The real board fills the screen width, so this is unlikely.

## Alternatives considered

| Approach | Why not (for now) |
|---|---|
| CSP library (python-constraint, OR-Tools) | Adds a dependency and hides the search we plan to explain later |
| Dancing Links / exact cover | Faster, but much harder to read and maintain. That speed isn't needed at N ≤ 16 |
| SAT solver | Requires an external solver. Overkill here, and hard to turn into step-by-step explanations |
| Region-by-region search order | A valid alternative. Row order is simpler and makes the row rule automatic. Revisit if profiling says so |
