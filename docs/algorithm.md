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

## Alternatives considered

| Approach | Why not (for now) |
|---|---|
| CSP library (python-constraint, OR-Tools) | Adds a dependency and hides the search we plan to explain later |
| Dancing Links / exact cover | Faster, but much harder to read and maintain. That speed isn't needed at N ≤ 16 |
| SAT solver | Requires an external solver. Overkill here, and hard to turn into step-by-step explanations |
| Region-by-region search order | A valid alternative. Row order is simpler and makes the row rule automatic. Revisit if profiling says so |
