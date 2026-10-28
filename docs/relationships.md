# Relationship preservation — 2026-10-28

Implemented source-derived enclosure and foreground image-layer relationships.
The public API and schema are unchanged. Existing groups, IDs, copy, fonts,
style runs, assets, stacking, opacity and rotations remain intact. No renderer,
asset, sample, schema, dependency or connector code was changed.

Local evidence (the directory retains the date this investigation started):

- [All 24 before/after comparisons](../artifacts/relationships-2026-10-27/index.html)
- [Four new sources / eight additional controls](../artifacts/relationships-2026-10-27/new-probes.html)
- [Updated source/output/candidate report](../artifacts/relationships-2026-10-27/generalization-after/index.html)
- [Machine-readable suite changes](../artifacts/relationships-2026-10-27/suite-delta.json)
- [Final offline Docker audit](../artifacts/relationships-final-docker-w1n9ifzu/verification.json)

These are ignored local artifacts, not submission inputs or official scores.
The pre-existing generalization report, tools, fixtures and user-created
`generalization-review.zip` were preserved. Before outputs use the pre-change
engine snapshot, not a newly invented baseline.

## Diagnosis and implementation

The original analysis had no representation for an enclosing mat spanning
multiple explicit groups. Layout therefore allocated it a foreground slot and
quality classified mat/child intersections as collisions. Similarly, the
translucent rotated bottle pair lost its overlap because the original collision
check understood neither the compositing evidence nor the cost of separation.
The old uniform fallback preserved those relationships but was rejected for
false collisions and often had much smaller type.

`spatial_relationships.py` now records confidence and evidence separately from
the input design and original unit partition. A likely container must be a
filled, sufficiently opaque rectangle behind multiple fully contained units,
with plausible canvas coverage, occupancy, and padded/balanced borders. Full
backgrounds, narrow stripes, ellipses, rotated panels and low-opacity washes do
not qualify. Competing enclosures remain soft; inference never closes an ancestor
graph across the design.

High-confidence image pairs require partial offset overlap, comparable geometry,
contrasting rotations, transparency or differing z-index, and intersection of
the fitted assets' alpha envelopes. Overlap alone, transparency alone, and
overlapping empty image-box padding are insufficient. Unrelated text overlap is
negative evidence. Missing assets remain present and provide no positive alpha
evidence. Pair matching is disjoint; explicit multi-element groups are never
split. This is deliberately conservative, not a universal intent classifier.

`relationship_layout.py` adds alternatives to the existing search: move supported
image pairs with a shared transform; derive panel bounds around repositioned
children; or reserve one panel region and try rows/columns of its independent
child units. The latter was needed after the new inset-panel probe exposed a
sparse uniform fallback with 12.5 px text. The final alternatives use 19 px in
portrait and 17 px in landscape. The separate nearby card stays outside.

Evaluation grants only supported pair exceptions and penalizes lost containment,
lost box/visible overlap, excess occlusion and altered relative layer geometry.
New near-total image occlusion and third-party intersections are not exempt.
Repair restores supported pairs together and wraps containers after child repair.
Ambiguous hints have small soft costs without hard assembly constraints or new
collision exemptions. See [team-contract.md](team-contract.md) for fields and
interfaces. Inference uses geometry/style/local asset bounds, never fixture IDs,
names, copy, asset-name rules, or evaluation-only intent annotations.

## Measured and visually inspected results

All 24 tasks were run through the real renderer. Exactly four design JSONs and
PNGs changed; the other 20 are byte-identical. Independent intent annotations
counted **24 lost parent-child containments → 0** across the two reviewed mat
outputs, and **2 lost foreground image-layer pairs → 0** across the collage
outputs. These are distinct counts: the evaluator's generic lost-overlap list
also includes mat/child pairs and should not be added to containment counts.

| Reviewed output | Minimum font before → after | Relationship result |
| --- | --- | --- |
| nested-studio-cards, 500×1000 | 14 → 15 px | All 12 children enclosed; compact three-card row |
| nested-studio-cards, 1250×300 | 14.4 → 14.4 px | All 12 children enclosed; card sizes unchanged |
| transparent-overlap-study, 500×900 | 18.59 → 18.59 px | Relative rotated image placement and overlap retained |
| transparent-overlap-study, 1200×260 | 17.6 → 17.6 px | Layered pair retained; slightly smaller images |

For the mat portrait, the header/card-heading/body sizes are 25/18/15 px.
The wide version uses 24/17/14.4 px (body rasterizes at integer 14 px). Portrait
image boxes are now three equal 99.4×99.4 px boxes, with visible alpha extents
43×69 px; previously one was 121.1 square and two were 89.4 square. Wide image
boxes remain 93×93 px with alpha extents 41×64 px. The mat is no longer an empty
detached rectangle, but portrait has substantial blank space above the card row,
and wide still has broad gaps between cards and a border reaching canvas edges.

The collage portrait images grow from 196.5×255.5 / 219.0×205.8 to
288.4×375.0 / 317.3×298.1 px. Visible alpha extents grow from 85×136 / 88×143 to
123×198 / 128×206 px. Wide images change from 167.9×218.2 / 209.6×196.9 to
164.3×213.7 / 180.8×169.8 px, with alpha extents 70×113 / 73×117 px. Recognizable
imagery and the meaningful overlap remain. The independent logo becomes smaller;
the decorative light disk still has no inferred attachment to the collage and
floats upward in portrait. Asset-alpha extents are bounding proxies before scene
rotation, opacity and occlusion, not exact visible-pixel measurements.

No selected output in the full 24-task suite has measured overflow, raw/rotated
clipping, unwanted annotation-aware collisions, group errors, schema errors or
protected-field changes. The unchanged adversarial index still has 5–6 px text,
and the shallow missing-contact-sheet has 7 px text. These remain visual failures
despite structural validity. The renderer's missing-asset labels remain unchanged.

New sources cover a two-row inset panel with an independent neighboring group,
an opaque rotated layered pair, an accidental overlapping-image control, and
decorative shapes behind separate groups. Their sources and before/after PNGs
were inspected; the accidental-overlap source is intentionally invalid. Across
eight outputs, lost containments fall **8 → 0** and lost image-layer pairs **2 → 0**.
Accidental overlap is removed, decoration does not become a container, and both
negative controls retain the old outputs. The new panel's wide text drops from
22 to 17 px in exchange for keeping the panel/children together; portrait rises
17 to 19 px. The new opaque collage stays at 22.09 px in portrait and rises
21.44 to 31 px in wide. Wide panel margins and portrait collage spacing are still
generous. No new selected output has overflow or unwanted collisions.

Candidate catalogs retain raw/effective scores and previews for all four reviewed
tasks. Final selected indices are 34, 18, 44, 80 in table order. Under the new
evaluator the old detached-mat outputs incur containment cost 102; old separated
collages incur layering costs 126.68 / 122.04. Selected relationship loss is zero
within floating-point tolerance. The old uniform fallback is now feasible but
scores 12.92 / 49.28 / 4.15 / 15.76 versus 4.47 / 4.84 / 1.14 / 1.54 selected.
This combines better generation with corrected collision handling and selection;
it is not simply an overlap exemption. All scores are local heuristics.

## Verification actually run

- **39/39 tests pass natively**: the existing 28 plus 11 relationship tests.
  Counterexamples cover accidental overlap, empty alpha padding, missing art,
  transparency/rotation alone, text intrusion, excessive image occlusion, partial
  explicit groups, background/decorative shapes, competing enclosures, nearby
  groups, non-transitive image matching, renamed IDs/shuffled order, immutability
  and preservation through candidate repair.
- Full 24-task suite passes selected-output structural/preservation checks;
  634 candidates evaluated with selection independently reproduced from catalogs.
  Eight new controls also pass; repeated calls produce identical new-control JSON.
- Independent Draft 2020-12 validation passes **720 design JSONs**, including
  sources, outputs and diagnostic candidates in the local artifact collection.
- Original samples rendered with the frozen-before/current-native engines have
  identical design JSON and PNG bytes. Protected file hashes and the pre-existing
  generalization work/archive are unchanged.
- **Final Linux/amd64 Docker build and offline original-sample runs pass**.
  Two fresh runs plus a fail-closed third audit produce all three JSON/PNG pairs;
  JSON bytes match and PNG pixels match direct real rendering. Renderer fallback
  was forbidden in the audit. All IDs (4/11/17), text/styles/assets/groups, image
  proportions, schema, rotated bounds and input immutability checks pass.
- Independent container-output schema verification passes 3 sources / 9 outputs.
  **39/39 tests also pass inside Linux/amd64 with `--network none`**.
- All six original-sample JSON/PNG files are byte-identical to the previously
  verified Linux checkpoint in `artifacts/checkpoint-verify.ndyzhhqj/run-1`.

Final Docker evidence is in `artifacts/relationships-final-docker-w1n9ifzu`.
The final Linux/amd64 image ID is
`sha256:f3d6a41eed7f30b8de9740e1355be2e687db0904ea1f7d4d2b7cbbc6f4d3451e`.
Docker became available during this resumed task; the earlier unavailable check
was superseded by these actual executions. No packaging fixes were needed.
The known Docker constant-platform lint warning and nonfatal Fontconfig
`reset-dirs` warning remain. Level 3 still has its intentional missing-asset
placeholder and 7 px legal text. This is amd64 emulation on an ARM host, not
verification of hidden benchmark performance or cross-platform pixel identity.

## Reproduction

Use the installed renderer environment (`/Users/vedu/miniconda3/envs/chameleon/bin/python`
for the native run here). Preserve a before-engine snapshot and the prior report
before editing runtime code. The actual suite commands were:

```sh
python -m tools.generalization sources --out artifacts/relationships-2026-10-27/generalization-after
# Source designs were unchanged from the inspected prior suite; copy its reviewed hash.
cp artifacts/generalization-2026-10-27/source-review.json artifacts/relationships-2026-10-27/generalization-after/source-review.json
python -m tools.generalization run --out artifacts/relationships-2026-10-27/generalization-after
python -m tools.generalization candidates --out artifacts/relationships-2026-10-27/generalization-after --tasks nested-studio-cards-t1 nested-studio-cards-t2 transparent-overlap-study-t1 transparent-overlap-study-t2
python -m tools.evaluate_relationships --before-engine artifacts/relationships-2026-10-27/before-engine --before-suite artifacts/generalization-2026-10-27 --after-suite artifacts/relationships-2026-10-27/generalization-after --out artifacts/relationships-2026-10-27
python -m unittest discover -s tests -v
```

The Docker directories were freshly created with `tempfile.mkdtemp`; the source
hash manifest used the preparation procedure in [submission-verification.md](submission-verification.md),
including the constraints file. Final commands (all exited zero):

```sh
docker build --platform linux/amd64 -t chameleon-engine .
VERIFY="$PWD/artifacts/relationships-final-docker-w1n9ifzu"
for RUN in run-1 run-2; do
  docker run --rm --platform linux/amd64 --network none \
    -v "$PWD/input:/app/input:ro" -v "$VERIFY/$RUN:/app/output" chameleon-engine
done
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" -v "$PWD/tools:/app/tools:ro" \
  -v "$VERIFY:/verification" --entrypoint python chameleon-engine \
  -m tools.verify_submission /verification
python -m tools.verify_submission "$VERIFY" --schema-only
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" -v "$PWD/tools:/app/tools:ro" \
  -v "$PWD/tests:/app/tests:ro" --entrypoint python chameleon-engine \
  -m unittest discover -s tests -v
```

The host schema-only command used the existing host Python/jsonschema environment,
not an added runtime dependency. For another audit, create fresh directories and
a current source-hash manifest; the harness refuses reused audit/direct outputs.

## Remaining relationship limitations

Connectors are deliberately unchanged. The two `three-node-process` outputs are
byte-identical to the known broken diagrams: bars move independently of nodes.
Diagram relationships are **not solved**. Decorative attachment, arbitrary deep
nesting, rotated/nonrectangular containers, layers inside multi-element explicit
groups, unrotated intended collages, and larger overlapping image assemblies are
not modeled by this targeted inference. Alpha envelopes can overestimate actual
pixel contact. Confidence is heuristic; unusual accidental arrangements can
still resemble intended compositions. Ambiguous hints stay soft rather than
granting broad collision immunity. Full readability on extreme targets remains
limited by content density and preserved group geometry.

No commit or push was made.
