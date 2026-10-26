# Visual-quality improvements

The public entry point, source invariants, supplied renderer and original 20
regression tests are preserved. New code is in `engine/horizontal.py`,
`engine/groups.py`, and `engine/relationships.py`, with integration in layout and
quality. The existing candidate families and conservative fallback remain.

## Diagnosis

The main bottleneck was **candidate generation**, with scoring a secondary
problem. The old extreme-banner winner stacked three foreground images in one
narrow column, split copy into poorly balanced vertical areas, and preserved
excessive label padding. The rotated ribbon's original bounding box consumed
height without giving its label usable space. Ordinary landscape candidates
also centered related text independently inside large slots.

The old winning banner already had zero local hard errors and did **not** invoke
repair. Its small fonts were the consequence of its allocated boxes, not repair
needlessly shrinking otherwise adequate boxes. Typography measurement itself
was kept unchanged in this pass.

A controlled candidate-pool comparison showed:

| Candidate generation | Scoring | Selected headline / body / smallest text | Product box |
| --- | --- | --- | --- |
| Previous | Previous | 9 / 6 / 5 px | 38.4 × 38.4 px |
| Previous | Stronger new costs | Same previous layout and sizes | 38.4 × 38.4 px |
| Measured horizontal allocations added | Stronger new costs | 13 / 8 / 7 px | 74.6 × 74.6 px |

Changing scores alone did not supply a better compromise. The new generator
creates that compromise, while explicit microscopic-text, headline-prominence,
image-recognition and text-cohesion costs help protect it during selection.
All these costs remain local heuristics, not the challenge's official rubric.

## Changes

- Measure complete copy at proposed font sizes before allocating height. Use a
  shared readability level with a larger headline and smaller fine print, rather
  than independently shrinking each item to whatever space is left.
- Explore wider media areas, a large primary image beside its companions,
  alternate image rows/columns, and one to three rows of compact groups.
- Compact only simple rectangle/label pairs. Keep normalized label centers,
  containment, IDs, membership and rotations. General groups retain the previous
  transform rules. No text, font family, style run, asset or styling field is
  rewritten; only permitted geometry and font size change.
- Add coherent text-block alternatives for linked source copy after substantial
  reflow. Penalize excessively separated related text, while keeping existing
  candidates available for validation and comparison.
- Penalize very small actual integer glyph sizes sharply, and independently
  penalize a headline losing prominence to secondary copy. Penalize tiny image
  short sides without looking at asset names or treating missing images specially.

## Supplied designs: measured results

Level 1 is unchanged. Level 2 retains all font and image sizes, while the
headline/subheading **box gap falls from 148.8 to 11.2 px**. The measured glyph-ink
gap falls from **152.8 to 15.3 px**, forming a coherent copy block.

| Level 3 measurement | Previous engine | Improved engine |
| --- | ---: | ---: |
| Headline font | 9 px | 13 px |
| Body font | 6 px | 8 px |
| Three badge labels | 9 px | 8 px |
| Action label | 8 px | 8 px |
| Rotated ribbon label | 5 px | 8 px |
| Legal font | 9.6 px (9 rendered) | 7 px |
| Logo box | 57.8 × 18.1 px | 71.7 × 22.4 px |
| Product box | 38.4 × 38.4 px | 74.6 × 74.6 px |
| Missing-asset element box | 51.1 × 22.7 px | 71.7 × 31.9 px |
| Text overflows | 0 | 0 |
| Unintended collisions | 0 | 0 |

The legal copy and three badges surrender some size to fund the headline, body,
ribbon and product. This is an explicit hierarchy/space tradeoff, not a claim
that every element got larger. The actual logo artwork is smaller than its box
because the supplied asset contains transparent space. Its recognition remains
limited at this target. The missing-asset placeholder remains the supplied
renderer behavior, including its clipped diagnostic label.

**The extreme case is improved, not fully readable at ordinary viewing size.**
Seven- and eight-pixel copy remains small; the dense content uses most of the
banner and leaves little breathing room. We did not prove full readability
infeasible: this is a finite heuristic search, not an optimality proof. No content
was deleted, hidden, collapsed, made transparent or regenerated to claim success.

## Additional cases and reserved checks

Three additional wide designs with different copy lengths and group counts were
used for tuning. Two keep their previous font sizes. The crowded case changes
headline/body from 14/8 to 16/11 px and grows the product box from 45.1 to
107.5 px square, while reducing some larger label/legal sizes for balance.

Four reserved wide cases were evaluated **after** the runtime was frozen. The
hash manifest is `artifacts/quality-tuning/frozen-before-holdout.json`; runtime
hashes were verified unchanged after evaluation. None of the reserved cases
was used for subsequent tuning.

| Reserved case | Body font before → after | Smallest font before → after | Main product box before → after | Result |
| --- | --- | --- | --- | --- |
| wide-a | 19.2 → 19.2 | 10.4 → 10.4 | 116.2² → 116.2² px | Unchanged |
| wide-b | 12 → 15 | 10.4 → 12 | 68.4² → 163.2² px | Larger copy/images; headline 26 → 22 px |
| wide-c | 12 → 12 | 10.4 → 10.4 | 65.3² → 65.3² px | Unchanged |
| real-d | 14 → 15 | 10.4 → 13 | 117.2² → 121.0² px | Coherent text block; headline 31 → 23 px |

All reserved outputs have zero measured overflow and unintended collision errors.
The real-only reserved case retains headline prominence but reduces its logo box
height from 28.2 to 22.7 px while enlarging the secondary product box. That is a
remaining image tradeoff, documented rather than hidden by the aggregate score.

Existing real assets are used in two tuning cases, a real-only portrait control,
a real-only landscape control, and the real-only reserved case. Some other cases
retain a deliberate missing asset. The real portrait control is unchanged;
the real landscape control keeps its font and image sizes and improves the copy
gap. The original synthetic landscape is unchanged. The original placeholder
portrait moves its image above a coherent text block and reduces that image box
from 230.8 × 288.6 to 188.0 × 235.1 px without changing font sizes. The square
control is unchanged. The synthetic extreme case gains larger body text at the
cost of a smaller placeholder box.

## Verification and artifacts

- 28 unittest tests passed, including eight new quality regressions; the original
  regression test file was not changed during this quality pass.
- All 16 selected designs passed preservation, positive-size, proportion,
  grouping, bounds, typography and collision checks.
- 64 PNGs were rendered with the real renderer: source, stretch baseline,
  frozen previous engine, and improved engine for each case. Representative
  before/after banners, real-asset controls and reserved outputs were inspected.
- All 64 report designs and three official output designs independently passed
  Draft 2020-12 schema validation.
- `python -m engine.main` refreshed all three files in `output/` and their PNGs.
  Their JSON and PNG pixels match the report's improved panels.
- Renderer, brand kit, schema, original inputs, and `engine/main.py` are unchanged.
  No commit or push was performed. Docker remains unverified on this host.

Open `artifacts/comparisons/index.html`. Its expandable tables show every actual
font size, rendered integer size, line count and foreground image box; its JSON
metrics include overflow/collision lists and text gaps. Scores on all panels
are recomputed with the current evaluator, allowing fair before/after comparison.
