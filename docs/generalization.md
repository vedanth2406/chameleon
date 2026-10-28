# Generalization evaluation — 2026-10-27

The unchanged checkpoint was evaluated on **12 new source compositions, each at
2 substantially different targets**. All 24 outputs preserve the checked design
invariants and render successfully, but native-size inspection exposes failures
in relational composition, readability, and allocation of space. These are local
development probes, not an unseen benchmark or official challenge scores.

Open the [source/output report](../artifacts/generalization-2026-10-27/index.html)
and [source-only review](../artifacts/generalization-2026-10-27/sources.html).
Images display at native CSS pixel size in scrollable containers, with full-size
PNG/JSON links, actual font/image measurements, and score breakdowns.
Generated artifacts are ignored by Git and must be regenerated on a fresh clone.

## What was held fixed

- Engine commit: `6e1bbdba0281b8ff4dae4bfc5a5505de7f134f4d`.
- All tracked files, including runtime code, original tests, dependencies,
  renderer, schema, samples, fonts and assets, have unchanged SHA-256 hashes.
- No engine tuning, asset generation/replacement, dependency installation,
  commit, or push occurred. New code is development-only:
  `tools/generalization_cases.py` and `tools/generalization.py`.
- Docker was unavailable: its daemon socket did not exist. Evaluation used the
  existing native environment at `/Users/vedu/miniconda3/envs/chameleon/bin/python`:
  Python 3.11.17, macOS ARM64, Pillow 13.0.0, skia-python 144.1, cr-renderer 0.1.0,
  renderer commit `a17e1fb9a732959dd6c21ae168d5ee09d74bd64f`. This is **not** a new
  Docker verification or a cross-platform equivalence claim.
- Python socket connections were blocked during fixture rendering, output
  evaluation, and candidate rendering. The converter was called directly;
  the orchestrator's fallback renderer cannot satisfy this evaluation.

## Fixtures and source acceptance

The fixtures are hand-authored compositions with independent geometry and copy;
they do not call or copy the original sample/synthetic fixture constructors.
The recurring bottle/logo artwork is supplied material, not newly generated art.
Ten sources use only real assets; two named missing-asset controls keep absent
references. The schema has only flat group IDs: nested-looking designs use
separate explicit groups inside a surrounding mat, with intended containment
recorded as **evaluation metadata outside the source design**.

| Composition | Source | Target 1 | Target 2 | Distinct construction |
| --- | --- | --- | --- | --- |
| gallery-triptych | 1000×650 | 420×900 | 1200×240 | Unequal image proportions and three image/caption groups |
| two-column-journal | 1000×760 | 600×900 | 1200×330 | Long masthead, style runs, two explicit editorial columns |
| asymmetric-field-poster | 760×1000 | 1000×420 | 360×760 | Large off-center art, narrow copy, inset note, isolated signature |
| programme-ledger | 960×600 | 420×900 | 1280×200 | Equal-priority schedule rows with labels, locations and art |
| nested-studio-cards | 900×800 | 500×1000 | 1250×300 | Three independent cards inside an enclosing translucent mat |
| transparent-overlap-study | 900×700 | 500×900 | 1200×260 | Ungrouped intentional image overlap, rotations and transparency |
| rotating-noticeboard | 1000×650 | 480×900 | 1200×220 | Three staggered rotated multi-element note groups |
| community-letter | 800×1000 | 1000×500 | 360×800 | Text-led letter, paragraph, salutation, sign-off and postscript |
| three-node-process | 1000×800 | 1200×360 | 480×960 | Peer nodes with a triangular connector network; no headline/CTA |
| unbreakable-reference-index | 1100×500 | 300×900 | 1000×120 | **Adversarial targets:** complete unbreakable identifiers |
| missing-inventory-pair | 1000×700 | 480×900 | 1100×250 | Two horizontal inventory cards, exactly one absent asset |
| missing-contact-sheet | 960×800 | 800×500 | 1200×100 | **Adversarial density:** six grouped tiles, exactly two absent assets |

Before any `resize()` calls, all sources were schema-validated and rendered.
Every source PNG was opened. This exposed white logo lettering on a light field
and misplaced diagram connectors: source fixtures were corrected with ordinary
dark backing shapes and properly positioned connectors. The bottle overlap was
made visibly meaningful. No existing asset pixels were changed. All final source
copy fits, rotated boxes/ink fit the canvas, and annotation-aware collision checks
pass. The two adversarial cases are reasonable at source size; their *targets*
are intentionally demanding. Fixtures were then frozen by a recorded hash.

Two ordinary source designs already reveal a semantic blind spot: the engine
flags 12 intended mat/child overlaps and one intended bottle overlap as hard
collisions. These warnings did not disqualify the reasonable source fixtures;
explicit authored intent and visual review distinguish them from accidental
source overlap. Intent annotations are never supplied to `resize()` or used to
change candidate selection.

## Checks and measurements

- 12 source PNGs and 24 selected-output PNGs rendered through the real converter.
- All 24 saved outputs passed exact ID multiplicities, protected content/styles,
  asset/group membership, positive sizes, target dimensions, image box ratios,
  rotated bounds, measured text overflow/ink bounds, and group geometry checks.
  No source mutation occurred.
- Zero engine hard errors and zero annotation-aware unwanted box collisions in
  selected outputs. This **does not imply visual success**.
- Independently validated **542 design JSON files** with Draft 2020-12:
  12 sources + 24 outputs + 486 effective candidates + 20 raw candidates that
  went through repair. The source stage was independently validated before runs.
- Existing **28 regression tests passed**, 3.968 seconds, in the native environment.
- Reconstructed every selection using the unchanged generate/evaluate/repair
  sequence and asserted exact equality with `resize()` output. None of the
  24 selected candidates required repair. All 486 raw/effective scores are saved.
- Exported **42 effective candidate PNGs plus 3 raw pre-repair PNGs** for eight
  diagnostic tasks. All additional unique previews were opened; duplicate PNGs
  were identified by byte hashes. The normal source/output preview inspection
  covered all 12 sources and all 24 selected outputs.

Per-task metrics include font sizes and rendered integer sizes, line counts,
overflow, rotated box/ink clipping, engine penalties, annotation-aware overlaps,
lost intended layers/containment, explicit group memberships, image box area and
source-relative area share, and mean normalized element-center displacement.

Image `visible_alpha_extent_px` measures the bounds of alpha >16 in the existing
asset after the renderer's contain/cover fitting, **before scene rotation,
instance opacity, and occlusion**. It is a recognition proxy, not a final visible
pixel mask or image-quality score. Likewise, box collision checks may overstate
image collisions because transparent padding is not removed. Center displacement
measures change, not whether reflow is good. Local penalties are not official
scores. Source fixture names/IDs and semantic annotations are evaluation-only.

## Ranked failure patterns

Counts below overlap. Font thresholds are warnings, while the accompanying
native-size observations identify actual visual failures.

### 1. Cross-group relationships are lost — 6 of 24 tasks

Both nested-card outputs detach the enclosing mat into a large empty rectangle.
All **12 intended parent/child containments** are lost in each. Both collage
outputs separate the deliberately overlapping bottles. Both process-diagram
outputs retain node groups but disconnect or cover the connectors, destroying
the triangular relationship. Individual group integrity can therefore pass
while the overall composition fails.

Candidate investigation:

- [Nested cards, target 2](../artifacts/generalization-2026-10-27/nested-studio-cards-t2/index.html):
  candidate 1 preserves the mat enclosure but has 12 engine collision errors,
  collision penalty **2400**, total **2449.28**, and 7.28 px body text. Selected
  candidate 9 has zero engine errors, total **2.20**, and 14.4 px body text,
  but turns the mat into an empty side panel. This is an analysis/validation and
  selection problem, with an additional readability compromise in the preserving
  candidate. No exported alternative solves both problems.
- [Collage, target 2](../artifacts/generalization-2026-10-27/transparent-overlap-study-t2/index.html):
  candidate 1 retains bottle overlap but gets an unwanted-collision error and
  **129.14** collision penalty. Selected candidate 11 separates them, total
  **1.98**. The overlapping candidate also has only 8.56 px minimum text and
  misplaced decorative light, so it is not a complete visual solution either.
- [Process, target 1](../artifacts/generalization-2026-10-27/three-node-process-t1/index.html):
  composition candidates 0/1 also have detached connectors. Candidate 1 scores
  **4.77** at 12.93 px labels; selected 6 scores **0.78** at 19.2 px. Neither
  scoring nor generation represents connector attachment. The preview evidence
  supports a generation limitation plus a missing relationship check, rather
  than a claim that selection rejected a fully working diagram.

### 2. Fit can still mean microscopic text or poor hierarchy

**5/24** outputs contain text below 12 px; **3/24** contain text below 8 px, all
in the adversarial cases. The narrow index has 5/7 px identifiers; its shallow
variant reduces every text element to 6–7 px. The shallow contact sheet has
7 px captions. The ordinary portrait inventory has **9.91 px** body text despite
large unused vertical space. The moderately resized contact sheet's **11.96 px**
captions are small but remain readable in the inspected preview; they are a
threshold warning, not equivalent to the 5 px failure.

- [Reference index, target 2](../artifacts/generalization-2026-10-27/unbreakable-reference-index-t2/index.html):
  selected candidate 4 scores **89.500**, with a 7 px heading and 6/7 px codes.
  Candidate 2 scores **89.642**, preserving a **22.4 px heading** and 16 px note,
  but has 5/6 px codes. Candidate 3 has a 22.4 px heading and 6/8 px codes, but
  nearly eliminates the logo's recognizable size: its image-recognition penalty
  is **104.65**, lifting its total to **153.71**. These are real compromises;
  candidate 2 is not strictly better on every measure. The tiny score difference
  between 2 and 4 shows weak protection of useful hierarchy. None of the 14
  generated feasible candidates exceeds a 6 px minimum.
- [Contact sheet, target 2](../artifacts/generalization-2026-10-27/missing-contact-sheet-t2/index.html):
  the best feasible minimum among all 12 candidates is **7 px**. Uniform fallback
  1 has 2.39 px text and total **2972.32**; selected 6 scores **71.60**. The tiny
  fallback is correctly rejected. The candidate family still lacks a readable
  dense-sheet arrangement; this is not evidence that one is mathematically
  impossible under every permitted layout.
- [Inventory, target 1](../artifacts/generalization-2026-10-27/missing-inventory-pair-t1/index.html):
  the best feasible minimum is **9.91 px** across all 12 candidates. Alternative
  5 raises one body paragraph to 14 px but lowers the other to 7 px. Selection
  avoids that imbalance; generation and the conservative group constraints
  limit the available compromise.

For the narrow 300 px index, the input words genuinely cannot fit at their
original sizes without breaking characters or reducing font size. The renderer
only wraps at spaces, and content must remain fixed. That physical width limit
should not be confused with the shallow 1000 px variant's poor allocation.
No selected output went through repair, so repair is not the cause here.

### 3. Group constraints and support artwork consume space poorly

Four visually flagged allocation cases are the two ledgers, portrait inventory,
and wide letter. Explicit rows/cards retain their source internal geometry while
large areas of the new canvas go unused, or secondary art gains excess emphasis.
The constraints preserving arbitrary multi-member groups are themselves part of
this tradeoff; reorganizing their contents would require a deliberate contract
or candidate-generation decision, not just moving the existing units.

- [Portrait ledger](../artifacts/generalization-2026-10-27/programme-ledger-t1/index.html)
  keeps 14 px text but only **27×16 px** alpha extents for its logos. Candidate 4
  scores **7.80**; source-like candidate 1 scores **22.65** with 9.17 px minimum
  text. The other previewed layouts also keep thin rows. More readable typography
  wins, but none exploits the tall format well.
- In the 1280×200 ledger, the three rows occupy a narrow central region and logos
  have **35×21 px** alpha extents. The text is readable; branding detail is weak.
- Portrait inventory keeps wide cards at the center, giving 9.91 px paragraph
  text and a **39×61 px** bottle alpha extent while leaving much of 480×900 empty.
- [Wide letter](../artifacts/generalization-2026-10-27/community-letter-t1/index.html)
  increases the signature backing to **500×160 px**, while the letter is 15 px
  across long lines. Candidates 4 and 15 both do this; they score **1.00** and
  **0.89**. Candidate 16 grows the logo further and is worse. Source-like options
  preserve emphasis better but use 9–9.4 px minimum text. This is an allocation
  tradeoff, not an overflow or content-preservation failure.

Separately, **4/24** outputs have at least one real asset with alpha extent short
side below 24 px: both ledgers, the shallow index, and the shallow contact sheet.
Small branding is not automatically a failure, but these previews show why box
size alone does not guarantee recognizable imagery.

## What worked and what the warnings mean

Editorial columns, the asymmetric field poster, the rotating noticeboard, and
the portrait letter remain largely usable across their targets. Text contents,
style runs, fonts, opacity, rotations, asset IDs and group membership survive.
Selected outputs show no measured text overflow or unintended box collisions.

The missing-asset controls deliberately show the supplied renderer's placeholder.
Its diagnostic label clips at small box sizes; that is **renderer behavior**, not
a font-overflow failure in a design text element, and no asset was invented to
hide it. Zero engine errors alongside broken mats/diagrams illustrates the limits
of heuristic checks. These examples do not establish performance on hidden inputs.

## Reproducing the separate suite

Use the existing development environment with the renderer installed. No package
installation is part of this evaluation. Replace `python` with that environment's
interpreter as needed, and use a new directory for another run.

```sh
python -m tools.generalization sources --out artifacts/generalization-review
```

Open `sources.html`, inspect all source PNGs and `source-validation.json`, then
record the manual review before running outputs:

```sh
python - <<'PY'
from pathlib import Path
import hashlib, json
p = Path('artifacts/generalization-review')
fixtures = json.loads((p / 'fixtures.json').read_text())
# Execute only AFTER inspecting and accepting the rendered sources.
(p / 'source-review.json').write_text(json.dumps({
    'approved_for_evaluation': True,
    'fixtures_sha256': hashlib.sha256(json.dumps(fixtures, sort_keys=True).encode()).hexdigest(),
    'notes': 'Record the actual source inspection here.'
}, indent=2))
PY
python -m tools.generalization run --out artifacts/generalization-review
python -m tools.generalization candidates --out artifacts/generalization-review --tasks \
  nested-studio-cards-t2 transparent-overlap-study-t2 three-node-process-t1 \
  unbreakable-reference-index-t2 missing-contact-sheet-t2 programme-ledger-t1 \
  missing-inventory-pair-t1 community-letter-t1
python -m unittest discover -s tests -v
```

The run phase refuses fixtures that differ from the reviewed hash. Candidate
exports include selected and composition/fallback variants, top ranked variants,
and alternatives chosen for font minimum, composition cost and image-scale cost.
No candidate is substituted into engine output. All candidate JSON and raw/effective
score catalogs remain available for further investigation.

Independent schema checks used the already-installed host `jsonschema` package.
Machine-readable local evidence includes `source-review.json`, `source-validation.json`,
`metrics.json`, `environment.json`, `verification.json`, `review.json`, and
per-task `scores.json`. Source, output and additional unique candidate PNGs were
inspected through image viewing. `review.json` contains per-output human findings;
`python -m tools.generalization report --out PATH` rebuilds HTML after updating
those observations. The `checkpoint-hashes.json` snapshot confirms that all
tracked project files remain unchanged.
