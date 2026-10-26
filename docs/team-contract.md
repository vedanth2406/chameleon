# CHAMELEON implementation contract

The engine is implemented and integrated through
`resize(source: dict, target_canvas: dict) -> dict`. One maintainer owns all engine,
test, tooling, and documentation files; the former three-person restrictions no
longer apply. The supplied renderer, brand kit, schema, samples, and
`engine/main.py` remain unchanged.

## Runtime boundaries

| Module | Interface | Responsibility |
| --- | --- | --- |
| `engine/analysis.py` | `analyze(source) -> Analysis` | Source units, backgrounds, decorations, importance, inferred roles and overlaps |
| `engine/typography.py` | `measure_text(element) -> dict` | Actual local Skia glyph metrics and converter wrapping |
| `engine/typography.py` | `fit_text(element, max_font_size=None) -> dict` | Independently copied element with only font size adjusted |
| `engine/layout.py` | `generate_candidates(source, target_canvas, analysis) -> list[dict]` | Complete independent designs, not patches |
| `engine/quality.py` | `evaluate(source, candidate, analysis) -> Evaluation` | Structural, preservation, geometric, typography and visual heuristics |
| `engine/quality.py` | `repair(source, candidate, analysis) -> dict` | Best-effort independent copy with protected fields restored, groups contained and text refitted |
| `engine/resize.py` | `resize(source, target_canvas) -> dict` | Input validation, candidate search, repair and deterministic selection |

`source` is a design containing `canvas` and `elements`, not the task wrapper.
`target_canvas` contains positive integer `width` and `height` in pixels.
Runtime helpers include `engine/geometry.py`, `engine/validation.py`,
`engine/horizontal.py`, `engine/groups.py`, and `engine/relationships.py`. Docker already
copies all of `engine/`. Tests live in `tests/`; development tools live in `tools/`.
The runtime imports neither. No new dependency is required beyond the supplied
renderer requirements. Install dependencies at build/setup time; execution uses
only local fonts/assets and makes no API calls, downloads, or model calls.

## Internal dictionaries

`engine/contracts.py` defines ordinary `TypedDict`s. They are metadata, never
extra fields added to output designs.

| `Analysis` field | Type | Meaning |
| --- | --- | --- |
| `units` | `list[LayoutUnit]` | Every original ID belongs to exactly one unit |
| `background_ids` | `list[str]` | Inferred near-full-canvas bottom layers |
| `decoration_ids` | `list[str]` | Ungrouped low-opacity shapes |
| `intentional_overlap_pairs` | `list[tuple[str, str]]` | Unique unordered pairs of original IDs with source layering evidence |
| `diagnostics` | `list[str]` | Missing assets and degenerate source geometry |

| `LayoutUnit` field | Type | Meaning |
| --- | --- | --- |
| `key` | `str` | Deterministic internal unit key, not a new element ID |
| `element_ids` | `list[str]` | Nonempty original membership |
| `source_bounds` | `tuple[float, float, float, float]` | Union of unrotated source boxes as `(x, y, width, height)` |
| `role` | `str` | Inferred hint: background, decoration, image, headline, text, fine_print, group, or shape |
| `importance` | `float` | Priority in `[0, 1]`, higher means more important |

Roles are never required input labels. ID spelling, asset filenames, text meaning,
and sample notes do not drive layout choices. A non-null `group_id`, including
an empty string, takes precedence over heuristics. Explicit groups are never
split, merged with other groups, or expanded to absorb ungrouped elements.
Conservative heuristic grouping pairs a shape with a single contained text label.

General groups share one transform. Groups containing images or rotations use
uniform scaling; unrotated text/shape groups may share an affine transform to
adapt their boxes. Their normalized relative positions and sizes are preserved.

A deliberately narrow exception permits compact padding for a two-member group
containing exactly one rectangle and one contained text label with the same
rotation. It preserves the label's normalized center within the rectangle and
keeps the full text box contained, including after rotation. Only box geometry
and font size change; group membership, angles and other styling stay fixed.
Arbitrary multi-element groups, image groups, differently rotated members, and
non-contained labels do not qualify. Quality validates this relation and repair
retains a valid compact pair rather than reinstating excessive source padding.
Font sizes are fitted independently in the original candidate families. Preserve the exact `group_id` fields and
original rotation, including the source renderer's per-element rotation centers.
Low importance and decorative status never authorize hiding/removal.

## Typography

`measure_text` returns full text measurements, without clipping to the box or
`max_lines`:

| Field | Type | Meaning |
| --- | --- | --- |
| `width` | `float` | Largest wrapped line's advance/ink width in pixels |
| `height` | `float` | Conservative full text height using actual font ascent/descent and line advance |
| `line_count` | `int` | Wrapped line count, including explicit breaks; zero for empty content |
| `overflow_x` | `bool` | Measured width exceeds box width |
| `overflow_y` | `bool` | Measured height exceeds box height or non-null `max_lines` is exceeded |
| `measurement_method` | `str` | Local Skia/converter method; identifies unknown-family fallback |
| `ink_bounds` | `tuple[float, float, float, float]` | Actual glyph ink bounds in the element's local coordinates, before rotation |

`ink_bounds` was added during implementation because checking only declared boxes
misses glyph overhang beyond a canvas edge. Quality rotates the ink about the
original text box's center, not the ink box's center.

Fonts load from `brand_kit/fonts` relative to the repository, not the working
directory. Font lookup and word wrapping reuse the supplied renderer helpers.
Measurement mirrors integer glyph sizes, style-span boundaries, spacing and
inclusive style-run ends in the installed renderer. The schema describes
end-exclusive style runs; preserve input runs exactly despite this renderer
mismatch. Never modify text/runs to compensate. Font fallback follows the
supplied local font manager; no font is fetched.

`fit_text` changes only `font_size`, preserving all nested data independently.
`None` caps the search at the existing font size; an explicit cap must be finite
and at least 1 px. Ordinary text uses integer search; spacing/mixed-style cases
use a quarter-pixel search because the converter's wrapping omits those effects
and fitting can be non-monotonic. If no searched size fits, return 1 px with
remaining overflow detectable. The function never claims that unresolved
content fits, truncates copy, changes line-height/spacing, or inserts wrapping
characters into the saved text. Measurement is conservative, not a guarantee of
identical raster coverage across renderer/Skia versions.

## Candidate search and selection

Candidates contain the original schema's complete `canvas` and `elements`.
The search includes mapped source centers for nearby aspect ratios, a uniform
whole-composition fallback, horizontal/vertical shelves, recursive partitions,
image/copy/action bands, and full-width fine-print strips. It tries different
space allocations and text priorities; no exact target sizes are special-cased.

Additional wide candidates allocate a full-height region to dominant foreground
imagery and place companion images/rotated labels alongside it. They calculate
text and group heights using actual measurements at a shared readability level,
with separate headline, body/label and fine-print priorities. A candidate is
rejected if those measured requirements do not fit; individual text is not
silently shrunk during this allocation. Alternatives include rows of compact
label groups and several media-region widths and arrangements.

For substantial aspect-ratio changes, adjacent, horizontally aligned source copy
also receives compact-block alternatives. This moves text together without
shrinking fonts; the existing alternatives remain available and collision checks
still apply. It fixes large empty gaps between related headline/subheading boxes.
Text wraps inside its allotted space; image boxes retain source proportions.
All candidates and returned elements are independent copies, including nested
style runs. Preserve source list order and stacking fields in returned designs.

`Evaluation` contains `hard_errors: list[str]`, `penalties: dict[str, float]`, and
`score: float`. Lower scores are better. Scores sum weighted nonnegative costs
for readability, hierarchy loss, collisions, spacing/alignment, composition
changes and image shrinkage. Additional costs penalize microscopic rendered
integer glyph sizes, headline/secondary-text hierarchy reversal, undersized
foreground-image short sides, and excessive gaps in linked copy. Readability
floors (9 px for ordinary text, 7 px for fine print, bounded by source size) are
heuristic cost thresholds, not declarations that those sizes are fully readable. These are local heuristics, not the official scorer.

Hard errors include invalid schema fields, changed protected fields, ID count
mismatches, nonpositive boxes, foreground-image distortion, group damage,
text overflow, out-of-canvas raw/rotated boxes or rendered ink, and material
unintended overlaps. Collision geometry intersects rotated rectangles; overlaps
above 1.5% of the smaller box are hard errors, smaller intersections still carry
a cost. Background/decorative layering and original unit relationships are
handled separately from foreground collisions. Source box overlap alone does
not prove that two unrelated foreground elements should overlap.

Schema validation reads the supplied local schema and implements its current
vocabulary (`type`, local references, required/properties, additionalProperties,
enums, numeric limits, array items/minItems, and type-conditional requirements).
It is not a general JSON Schema implementation. Regression artifacts are also
checked with an independent Draft 2020-12 validator when available.

`repair` restores fields from the source, removes extra/duplicate IDs, restores
missing IDs, corrects image proportions and group transforms, contains units,
and refits text. It does not promise to solve arbitrary collisions. Every repair
is re-evaluated. `resize` selects by `(hard-error count, score, generation order)`,
so feasible candidates always beat infeasible ones and ties are deterministic.
If no candidate is fully feasible, it returns the least-violating result with a
`RuntimeWarning` listing failures. Consumers must retain that diagnostic; an
impossible target is not silently declared valid. Invalid inputs (including
nonunique IDs or degenerate boxes) raise `ValueError`; missing assets do not.

## Preserved invariants

- Every source ID appears exactly once. Never invent or remove an element.
- Preserve text content, font families/weights/styles, style runs, asset
  references and group IDs exactly, including absent/null distinctions.
- Geometry and text `font_size` are the only fitting controls. Preserve all other
  fields: colors, opacity, rotation, stacking, alignment, line height, letter
  spacing, image fit, corner radius, strokes, and custom element properties.
- Preserve every non-background image's **source box** aspect ratio. Intrinsic
  asset aspect ratio and `fit: cover` do not grant exceptions.
- Never mutate source, target, analysis or another candidate. Deep copies prevent
  later output edits from changing the source.
- Never hide content, zero-size elements, make them transparent, or regenerate,
  redraw or replace assets. Missing asset IDs remain present; only the supplied
  renderer produces its existing missing-asset placeholder.
- Do not hardcode sample IDs, copy, filenames, counts, or exact target dimensions.
  Tests/tools may refer to fixtures; runtime decisions must generalize.

See [development.md](development.md) for checks, rendered comparisons, and known
visual/submission limitations. No automatic commit or push is part of this work.
