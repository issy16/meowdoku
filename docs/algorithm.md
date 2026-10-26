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
5. **D6 contradiction by assumption** (R7.9), only when D1–D5 find nothing.
6. **Nothing found:** "No simple step found; try Solve." Hints never reveal
   the solution (R7.6).

| Rule | Name | Statement |
|---|---|---|
| D1 | Cat neighborhood | A placed cat rules out every other cell in its row, column, and region, plus its 8 neighbors |
| D2 | Last open cell | A row, column, or region with no cat and exactly one open cell must have its cat there |
| D3 | Confinement | If a region's open cells all lie in one row, the other cells in that row are ✕ (same for columns). Reverse: if a row's open cells all lie in one region, the region's other cells are ✕ |
| D4 | Pigeonhole | If k regions have all their open cells inside the same k rows, every other cell in those rows is ✕ (same for columns). D3 is the case k = 1 |
| D5 | Blocking | An open cell is ✕ if a cat there would rule out every open cell of some other row, column, or region |
| D6 | Contradiction by assumption | Suppose an open cell has a cat (or is empty) and apply D1–D5 until they stop. If that leaves a row, column, or region with no room for its cat, or puts two cats in one unit or next to each other, the cell gets the opposite mark |

- D3–D5 only consider rows, columns, and regions that have no cat yet. For a
  unit with no open cells left, "all its open cells" would be vacuously true.
- Rules are checked in this fixed order, and cells are scanned in row-major
  order, so hints are deterministic (R7.4).
- D4 checks groups of regions up to size N/2. That's at most a few thousand
  groups for N ≤ 16, which is fast enough and easy to read.

### D6 Contradiction by assumption

D6 lives in `assume.py`, apart from `deduce.py`, so `find_deduction` stays
D1–D5 and only `hints.py` puts D6 after it.

- **Why it's sound.** Each D1–D5 step holds in every solution that matches
  the marks (R7.7). If assuming a mark leads, step by step, to a broken
  board, no solution has that mark, so every solution has the other one.
- **A branch without a contradiction proves nothing**, even one that ends in
  a complete valid board: concluding from it would assume the solution is
  unique.
- **Bounded.** One assumption at a time, followed only by D1–D5. D6 never
  nests assumptions, so it never turns into trial-and-error search.
- **Shortest proof.** Every open cell is tried in row-major order, a cat
  before empty. The proof with the fewest D1–D5 steps wins; ties go to the
  first one found. Once a proof is found, later branches stop as soon as
  they'd be as long, which keeps D6 cheap.
- **Already broken boards.** If the marks themselves already break the
  board, D6 finds nothing. `hints.py` reports mistakes before it gets here.
- **The hint** highlights the assumed cell and the unit that breaks. Its
  `steps` explain, in order: where to look, the assumption, each D1–D5 step
  that followed, why the board breaks, and which mark follows. The GUI shows
  only the short `reason` for now. `trace` keeps the D1–D5 deductions
  themselves, for tests.

**Cost.** D6 runs D1–D5 to a standstill twice per open cell, so its cost
is mostly D1–D5 failing at the end of each branch. To keep that down, D4
and D5 were sped up without changing what they return (checked against the
old code on 3,000 random boards): units and `ruled_out_by` are cached per
puzzle, D4 skips groups of regions that already span too many lines, and
D5 works out each unit's open cells once.

Measured when D6 was added:

- D1–D5 stall on the real board `IMG_7117` with 29 open cells. With D6,
  hints solve it in 32 hints. Each D6 proof takes 3–5 steps, and
  `next_hint` takes at most about 0.15 s.
- Random 10×10–12×12 boards played out with hints: at most 0.73 s per D6
  hint, including boards where D6 finally finds nothing.
- **Known limit:** column stripes (each column its own region, so every
  group of regions fits D4 exactly) is the worst case for D4: 0.9 s at
  10×10 and 4.4 s at 12×12 when D6 finds nothing. Real game boards don't
  look like this.

### Module boundaries

- `deduce.py` implements D1–D5 using only `Puzzle` and `BoardState`. It
  never imports `solver.py`.
- `assume.py` implements D6 on top of `deduce.py`. It never imports
  `solver.py` or `rules.py`.
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

`image_import.py` turns a screenshot into the text grid and the marks in five
steps. Each step is a separate function, so tuning one doesn't disturb the
others.

The real game draws the board as a white rounded card of **rounded colored
tiles with white gaps** between them, on a beige page. There are no grid
lines and no region borders: regions are shown only by tile color.
(Measured on `tests/fixtures/screenshots/IMG_7128.jpg`: 105 px tiles,
9 px gaps, about 8 px corner radius.) A ✕ is a thick white X across most of
a tile; a cat is a black and white cat face covering most of a tile, with
the tile color still visible around it (`IMG_7117.PNG`).

This program's own window (R9.6, `gui-*` fixtures) draws the same kind of
board, with a lucky cat face (white, dark outlines) for a cat. It also
shows Solve's answer as gray-outlined cats, and Hint rings (orange or red) in the
gaps around tiles. A whole-window screenshot adds a title bar and, from
macOS, a transparent shadow, which is laid over white when the image is
opened.

1. **Find the board (`find_board`).** Read the page color from the image
   corners. Tile pixels are those that differ by more than 40 in some color
   channel from white, the page color, and the window's two ring colors.
   Rows where at least 30% of the
   pixels are tile pixels form horizontal bands. Weaker rows (at least 4%)
   between two such rows join them, since they cross tiles covered by cat
   faces and ✕ marks rather than a white gap; this keeps a board whole when
   it fills only part of the image width, as in a wide window screenshot.
   Gaps that are small next to the runs on both sides (the white gaps
   between tile rows) are bridged. Headers, icons,
   buttons, and ad banners make short, wide bands. The board is the largest
   band whose colored area is square. Within a band, columns are banded the
   same way and the widest column band is the board, so tile-colored pixels
   off to the side (a window's shadow) don't widen it. This works on full,
   uncropped phone screenshots and whole-window screenshots.
2. **Count the cells (`count_cells`).** For every pixel column (and row) of
   the board, measure what share is tile pixels. A gap between tiles is white
   along the whole board, so its share is near zero (below 25%). A ✕ or a cat
   face covers only part of any line through a tile, so tile lines stay well
   covered even when every tile has a mark. The median spacing between gaps
   gives N, which must agree in both directions.
3. **Read cell colors (`cell_color`).** Sample a 16×16 grid over each tile
   and skip white pixels (gaps, ✕ marks, cat faces), black ones (cat fur,
   outlines), and neutral grays (channels within 10 of each other: the
   outlines of Solve's cats). The most common remaining color is the tile's
   color.
4. **Group colors into regions (`group_colors`).** Join cells whose colors
   are within RGB distance 28, in chains. The real game's 10 colors are at
   least 64 apart. There must be exactly N groups, otherwise raise
   `ImageImportError` ("found 6 region colors; expected 7"). Label groups
   `A`, `B`, … in row-major order of first appearance, then pass the text
   grid to the normal parser, which validates it (R4).
5. **Read the marks (`read_mark`).** Sample the middle of each tile (25–75%).
   At least 12% black means a cat; otherwise at least 15% neutral gray means
   one of Solve's cats, which reads as empty; otherwise at least 12% white
   means a ✕; otherwise the tile is empty (R9.1a). On `IMG_7117.PNG` the
   measurements are far from the 12% thresholds:

   | Tile | Black | White |
   |---|---|---|
   | Cats (5) | 43–46% | 23–26% |
   | ✕ (75) | 0% | 49–57% |
   | Empty (20) | 0% | 0% |

   In window screenshots, lucky cats measured 20–30% black, ✕ marks 0%
   black, and Solve's cats 27–37% neutral gray against at most 5% for ✕
   marks.

**History.** The first version (Milestone 8) guessed at a board with a dark
frame, grid lines, and thick region borders. The real screenshot has none of
those, so step 1 was replaced. It first took the box around *all* tile pixels,
which needed a cropped screenshot. Banding the rows, added for
`IMG_7114.PNG`, made full screenshots work. `IMG_7117.PNG`, the first board
with marks, broke two steps:

- **Step 2:** finding gaps by color change mistook the white ✕ strokes for
  gaps. It now uses tile coverage instead.
- **Step 3:** sampling near the tile edges hit the cat face, which covers
  most of the tile. It now skips white and black pixels instead.

Step 5 was added at the same time, when marks went from ignored to read.

**Status.**

- **Real screenshots:** all three read correctly, regions and marks.
  - `IMG_7128.jpg`: a cropped 10×10 empty board.
  - `IMG_7114.PNG`: a full 1206×2622 phone screenshot of another 10×10
    empty board, with the header, rule card, buttons, and an ad banner.
  - `IMG_7117.PNG`: a full phone screenshot of a 10×10 game in progress,
    with 5 cats and 75 ✕ marks.

  All expected grids and marks were transcribed by Claude and checked
  against the game by the owner. Each grid also has exactly one solution. In `IMG_7117`, all 5 transcribed cats are in
  that solution and no ✕ is on a solution cell. Copies of both also read correctly when shrunk to a third
  of their size or saved as JPEG quality 40. Each takes about 0.5 s.
- **Synthetic screenshots:** drawn in the measured style, from 4×4 to 12×12,
  as PNG and JPEG, with and without cats and ✕ marks drawn like the real
  ones, both cropped and inside a full phone screen. Deliberately breaking ✕
  detection makes 22 of these tests fail.

**Known limits:**

- Only one real board with marks has been seen. Highlighted tiles, if the
  game has them (a selected tile, or a conflict shown in red), haven't been
  seen either.
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
