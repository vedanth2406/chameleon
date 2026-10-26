# Development and evaluation

For the pinned Linux/amd64 checkpoint, offline sample runs, real-renderer audit,
and exact commands, see [submission-verification.md](submission-verification.md).
All 28 regression tests passed again in the rebuilt image, and the sample
JSON/PNG files match the previous verified outputs byte-for-byte. Native comparison results
and Docker results are recorded separately because font measurements can differ
between dependency/platform environments.

Use Python 3.11 with the pinned `requirements.txt` and its Linux constraints.
The Docker image is the verified runtime; native package availability and font
measurements can differ. In this workspace
the existing environment is `/Users/vedu/miniconda3/envs/chameleon/bin/python`
(Python 3.11). Its package inventory was not used to produce the runtime lock.
Checkpoint dependencies were installed only during the Docker build.

```sh
python -m unittest discover -s tests -v
python -m tools.evaluate --synthetic --wide all
```

The report opens at `artifacts/comparisons/index.html`. It includes source,
original stretch baseline, and selected engine result for all three supplied
tasks, the original synthetic compositions, additional wide compositions, and
real-asset controls. Use `--before-dir artifacts/quality-before` in this workspace
to include the frozen previous-engine outputs as a fourth panel. Each panel links its full-size PNG and
JSON; `metrics.json` contains scores, violations, font minima, timings, candidate
counts, and real-renderer warnings. The original baseline is preserved only in
`tools/baseline.py`, outside the runtime engine.

The report calls `renderer.converter.convert.render_design_to_png` directly.
A missing renderer raises an error; the orchestrator's box/label fallback is
never accepted as a successful comparison. Python socket connections are blocked
during report generation. The real renderer's missing-asset placeholder is
expected, and is distinct from the orchestrator's fallback renderer.

Runtime helpers are under `engine/`; tools/tests/artifacts are not Docker inputs.
`engine/main.py` and the official input/output directories are not changed by the
comparison tool. Use `--out PATH` for another local report location; paths inside
`input/` or `output/` are rejected.

## Regression coverage

The unittest suite covers ID multiplicities, nested immutability, protected
content/styles, source-box image ratios (including `cover`), explicit and inferred
groups, empty-string group IDs, intended and accidental overlaps, rotated box
bounds, renderer wrap parity/ink bounds, long text, mixed style runs, letter
spacing, explicit newlines, maximum lines, impossible fitting, invalid inputs,
repair, independent candidates, deterministic/offline execution, and near-aspect
composition preservation. It includes different counts, aspect ratios, renamed
IDs, shuffled order, text-only, image-only, and background-only designs.

All comparisons use actual brand fonts and the supplied rendering pipeline.
The HTML report and PNGs were visually inspected locally. The original synthetic fixtures
include deliberate missing image references; newer controls also use the supplied
bottle and logo assets. No replacement assets are generated.

## Visual limitations and submission scope

- The extreme supplied banner remains dense: body/group text is 8 px and legal text is 7
  px in the current selected design even though the text fits its measured box. The full-width fine-print strip
  is more legible than uniform shrinking, but this is not a production-ready
  typographic solution to fitting every original word into a tiny banner.
- Foreground images are proportional, but logos/products can become too small
  to recognize at extreme ratios. Actual opaque pixel coverage can be much
  smaller than an asset's declared box.
- Missing-asset placeholders remain present and may have clipped diagnostic
  labels at small sizes; this behavior belongs to the supplied renderer.
- Background and decoration inference is conservative and based on geometry,
  stacking and opacity. It cannot understand arbitrary artwork or designer intent.
  Grouping arbitrary overlapping foreground art may need richer heuristics.
- Collision checking uses rotated boxes, not per-pixel image masks. Font height
  is conservative. Some source styling (including poor contrast or source
  transparency) remains as supplied. No colors or assets are changed to mask it.
- A local score or zero hard errors is not an official quality verdict. Impossible
  targets return a warning and the least-violating candidate. The search is a
  finite heuristic, not a proof that no better layout exists.
- The supplied converter and schema disagree on style-run endpoint semantics.
  The engine preserves the source runs and measures the renderer's behavior.
- Docker was unavailable on the implementation host. The supplied Linux/amd64
  image build and `--network none` container run still need verification on a
  Docker host. Python tests/report blocked network connections, which is useful
  evidence but not a substitute for that container test.
- The required Adobe Express viewer add-on is outside this engine implementation
  and is not provided here. Final official scoring and submission remain untested.

The unchanged Docker workflow is:

```sh
docker build --platform linux/amd64 -t my-chameleon-engine .
docker run --rm --network none \
  -v "$PWD/input:/app/input" -v "$PWD/output:/app/output" my-chameleon-engine
```

## Initial implementation verification

- All 20 unittest tests passed, including the parameterized composition/aspect
  cases and the actual font/renderer helper checks.
- Imported all runtime modules and compiled every engine, tool and test source.
- Rendered 21 comparison PNGs: seven cases, each with source/baseline/improved.
  Selected designs had zero local hard errors. PNG inspection led to fixes for
  oversized buttons, text allocation, fine-print placement and a synthetic
  fixture's incorrectly sized background.
- Ran the unchanged `engine.main.main()` on all three samples with its output
  directory redirected to `artifacts/runner`, socket connections blocked, and
  the placeholder fallback replaced by a failing assertion. All runs were OK.
- Independently validated all 24 design artifacts (21 comparisons plus three
  runner results) and all three supplied sources with `jsonschema`'s
  `Draft202012Validator` in the existing base Python environment.
- Verified no diffs in the renderer, brand kit, schema, samples, or `main.py`.
  `git diff --check` passed. No commit or push was made.

## Current visual-quality verification

See [visual-quality.md](visual-quality.md) for the diagnosis, before/after numbers,
reserved-case evaluation, and tradeoffs. The current pass ran 28 tests (the
original 20 are unchanged), rendered 64 comparison PNGs across 16 cases, and
independently schema-validated 67 design artifacts including the three refreshed
official outputs. All 16 selected designs had zero local hard errors.

The requested `python -m engine.main` was run using the installed Python 3.11
CHAMELEON environment. `output/` now contains the selected designs and real
renders, matching the report's improved JSON and PNG pixels. No protected input,
renderer, brand-kit, schema, or main module was changed.

Reproduce the full before/after report in this workspace:

```sh
python -m tools.evaluate --synthetic --wide all --before-dir artifacts/quality-before
```

`artifacts/quality-before/` contains the frozen prior engine and task/output
snapshots. Reserved cases were not inspected until tuning was frozen; the runtime
hashes remained unchanged through their evaluation. These local artifacts are
ignored by Git. On a new checkout without snapshots, omit `--before-dir` to
render source/stretch/current comparisons.
