# Checkpoint proposal — 2026-10-26

The proposed checkpoint contains **30 files** relative to the current Git
HEAD. This includes the existing uncommitted engine implementation, development
tools, regression tests, and documentation from prior work. None of the engine
or test files changed during today's dependency-pinning verification.

No files were staged, committed, or pushed. This is a reviewable proposal, not
an executed commit.

## Exact proposed files

```text
.dockerignore
.gitignore
Dockerfile
README.md
constraints-linux-amd64.txt
docs/checkpoint.md
docs/development.md
docs/submission-verification.md
docs/team-contract.md
docs/visual-quality.md
engine/analysis.py
engine/contracts.py
engine/geometry.py
engine/groups.py
engine/horizontal.py
engine/layout.py
engine/quality.py
engine/relationships.py
engine/resize.py
engine/typography.py
engine/validation.py
requirements.txt
tests/__init__.py
tests/test_engine.py
tests/test_visual_quality.py
tools/__init__.py
tools/baseline.py
tools/evaluate.py
tools/quality_cases.py
tools/verify_submission.py
```

Today's changes are the build/dependency pins, Git/Docker exclusions, README,
and updates to `docs/development.md`, `docs/submission-verification.md`, and this
proposal. The other listed files carry forward the working implementation and
checks already present before this task.

## Excluded and preserved

- Generated `artifacts/`, comparison reports, verification outputs/logs, and
  `output/` results are ignored and excluded. The tracked `output/.gitkeep` is
  unchanged and is not part of the proposed diff.
- `comparisons.zip` and `comparisons-v2.zip` remain on disk and are now ignored.
- Python caches, local environments, and test/tool caches are ignored.
- Original `input/`, `brand_kit/`, the design schema, all supplied `renderer/`
  files, and `engine/main.py` are unchanged; they are already tracked and are
  not part of the proposed diff.
- `.dockerignore` limits build context to runtime/build inputs. Development
  tests/tools are mounted read-only only for verification containers.

## Verification result

The uncached Linux/amd64 rebuild succeeded. Two fresh `--network none` runs,
the fail-closed real-renderer audit, independent schema and preservation checks,
and all 28 existing tests passed. All 44 installed distribution versions match
the prior verified Linux image and the constraints file. The renderer's exact
resolved Git commit matches its requested pin. All six sample JSON/PNG files
are byte-identical to the previous verified outputs. Engine, tests, samples,
assets, fonts, renderer, and schema hashes are unchanged from task start.

See [submission-verification.md](submission-verification.md) for exact commands,
image IDs, recorded results, local artifact paths, warnings, and remaining
reproducibility and visual limitations. The extreme banner's 7 px legal text
and intentional missing-asset placeholder remain; there were no layout changes.
