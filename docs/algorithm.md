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

## Planned optimization (only if measurements show it's needed)

**Region dead-end pruning:** after placing a cat, abandon the branch if some
unused region has no legal cell left in the remaining rows. It's cheap to
check and catches many dead ends early. It will be added only with
before-and-after timings, and the oracle tests must keep passing unchanged.

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
2. **Rule violations:** use `rules.find_violations` on the placed cats.
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

## Screenshot import

1. Load the image with Pillow and convert it to RGB.
2. Find the board: the largest roughly square area enclosed by grid lines.
3. Find N by counting the grid lines along each edge (they must agree).
4. Find each cell's region color: the most common color inside the cell,
   excluding a margin along the grid lines. A cat or ✕ icon covers only part
   of the cell, so the background still wins and marks are ignored (R9.1a).
5. Group cell colors into regions. Colors close together (by RGB distance)
   form a group. If there aren't exactly N groups, raise `ImageImportError`.
6. Label the regions `A`, `B`, … in row-major order of first appearance, then
   hand the text grid to the normal parser.

The thresholds are tuned against the sample screenshots in
`tests/fixtures/screenshots/`, including at least one in-progress board with
cats and ✕ marks. Tests also use synthetic images generated with known
regions, with and without drawn marks, so detection can be checked without
real screenshots.

## Alternatives considered

| Approach | Why not (for now) |
|---|---|
| CSP library (python-constraint, OR-Tools) | Adds a dependency and hides the search we plan to explain later |
| Dancing Links / exact cover | Faster, but much harder to read and maintain. That speed isn't needed at N ≤ 16 |
| SAT solver | Requires an external solver. Overkill here, and hard to turn into step-by-step explanations |
| Region-by-region search order | A valid alternative. Row order is simpler and makes the row rule automatic. Revisit if profiling says so |
