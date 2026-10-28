# Submission verification

## Relationship update — 2026-10-28

**PASS.** The final relationship-aware working tree was rebuilt for Linux/amd64
with the unchanged supplied Dockerfile and pinned dependencies. Two fresh
`--network none` sample runs, a third fail-closed real-renderer audit, independent
schema validation, and all **39 regression tests** passed. No packaging or
renderer changes were needed. Evidence is in
`artifacts/relationships-final-docker-w1n9ifzu`; exact commands, visual tradeoffs,
the 24-task rerun and remaining connector failures are recorded in
[relationships.md](relationships.md). The checkpoint record below is retained
as historical evidence; this update has not been committed or pushed.

## Reproducible checkpoint — 2026-10-26

**PASS.** Rebuilt Linux/amd64 from pinned dependencies with `--no-cache`, ran
original samples twice with `--network none`, repeated the fail-closed
real-renderer audit and independent schema checks, and passed all 28 existing
regression tests. No engine, layout, tests, renderer, original sample, asset,
font, or schema changes were made in this checkpoint.

### Dependency provenance and build changes

The previously verified image was still available as
`sha256:589aed83d84fa1e8173f55b1a48827fa7e67f005403ec3c0d738eef59a6d25c0`.
Its distributions and `cr-renderer` installation provenance were read directly
inside a Linux/amd64, network-disabled container and compared with the saved
2026-10-25 verification record. They matched. No host Conda package list was used.

- `requirements.txt`: Pillow **13.0.0**, plus cr-renderer from
  `https://github.com/CyberAgentAILab/cr-renderer` at commit
  `a17e1fb9a732959dd6c21ae168d5ee09d74bd64f`.
- `constraints-linux-amd64.txt`: all **44** installed distributions from that
  image, including transitive runtime packages and inherited packaging tools.
  `requirements.txt` includes `-c constraints-linux-amd64.txt`; the Dockerfile
  copies both files before pip resolves/install dependencies.
- The Docker base is pinned to the verified `python:3.11-slim` digest
  `sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377`.
- `.dockerignore` admits only build/runtime inputs and excludes caches. Tests,
  development tools, reports, Git history, and ZIP archives stay outside the
  build context. `.gitignore` also excludes comparison ZIPs and local caches
  and environments. Nothing was deleted or staged.

The resulting image is
`sha256:edaa62e9a9b8812d25a479304e922897bed953d4bd0c248ef0cd852279809f09`,
confirmed Linux/amd64, Python **3.11.17** / `x86_64`. All 44 installed versions
exactly match both the previous container and the constraints file. The renderer's
resolved commit and new `requested_revision` both equal the pinned commit.

This is a dependency-version checkpoint, not a fully hermetic or byte-identical
image build: apt repository packages and isolated Python build backends are not
locked, package downloads are not hash-locked, and build-time network access is
still required. Runtime needs no network. Cross-platform rasterization is not
promised; Linux/amd64 remains the verification reference.

### Fresh runs and actual results

Evidence is in
[`artifacts/checkpoint-verify.ndyzhhqj/`](../artifacts/checkpoint-verify.ndyzhhqj/).
`artifacts/submission-latest.txt` and `artifacts/checkpoint-latest.txt` point there.
These are ignored local artifacts, not proposed commit contents. The previous
run directory and existing `output/` and comparison reports were preserved.

| Check | Actual result |
| --- | --- |
| Uncached pinned build | PASS, exit 0; no dependency/build failures |
| Two ordinary offline runs | PASS, exit 0 each; exactly 3 JSON + 3 PNG per fresh directory |
| Real renderer | PASS; 3 recorded calls with fallback forbidden; all normal/audit PNG pixels match direct rendering |
| Independent schema | PASS; Draft 2020-12 / jsonschema 4.26.0; 3 sources and all 9 normal/audit output JSONs |
| Preservation and geometry | PASS; IDs exactly once, content/styles/fonts/assets/groups unchanged, foreground image proportions intact; no hard errors, text overflow, or unwanted collisions |
| Deterministic design JSON | PASS; byte-identical across both normal runs and audited third run |
| Comparison with previous verified image | PASS; all 3 JSON files and all 3 PNG files byte-identical to the previous run |
| Dependency resolution | PASS; all 44 distributions exactly match previous image and constraints; renderer URL/commit match |
| Existing regression tests | PASS; 28 tests in 8.762 seconds |
| `pip check` | PASS; `No broken requirements found.` |
| No layout/source/test changes | PASS; SHA-256 of all 40 runtime/protected/test files match pre-change snapshot |

See [`verification.json`](../artifacts/checkpoint-verify.ndyzhhqj/verification.json),
[`schema-verification.json`](../artifacts/checkpoint-verify.ndyzhhqj/schema-verification.json),
and [`checkpoint-verification.json`](../artifacts/checkpoint-verify.ndyzhhqj/checkpoint-verification.json).
The last file records package equality, renderer revision equality, each sample's
before/after byte equality, source/test hashes, and the rebuilt image ID.
The same Fontconfig warning and Docker platform lint warning seen in the first
verification remain nonfatal. No check was relaxed to obtain a pass.

### Commands used

From the repository root, the dependency inventory was captured with:

```sh
docker run --rm --platform linux/amd64 --network none --entrypoint python \
  sha256:589aed83d84fa1e8173f55b1a48827fa7e67f005403ec3c0d738eef59a6d25c0 \
  -c 'import json,importlib.metadata as m; print(json.dumps({"packages":{d.metadata["Name"]:d.version for d in m.distributions()},"renderer_origin":json.loads(m.distribution("cr-renderer").read_text("direct_url.json"))},indent=2))'
```

A fresh `checkpoint-verify.*` directory was allocated with `tempfile.mkdtemp`,
with empty `run-1`, `run-2`, `audit`, and `direct` directories. For repeating the
audit, use the preparation snippet in the initial verification below with prefix
`checkpoint-verify.` and **add `constraints-linux-amd64.txt` to the hashed build
inputs**. Substitute the newly allocated path everywhere; do not reuse this
completed audit directory. The pre-change snapshot additionally included tests.

```sh
docker build --no-cache --platform linux/amd64 -t chameleon-engine .
docker image inspect chameleon-engine

for chameleon_run in 1 2; do
  docker run --rm --platform linux/amd64 --network none \
    -v "$PWD/input:/app/input:ro" \
    -v "$PWD/artifacts/checkpoint-verify.ndyzhhqj/run-$chameleon_run:/app/output" \
    chameleon-engine
done

docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" -v "$PWD/tools:/app/tools:ro" \
  -v "$PWD/artifacts/checkpoint-verify.ndyzhhqj:/verification" \
  --entrypoint python chameleon-engine -m tools.verify_submission /verification

python -m tools.verify_submission artifacts/checkpoint-verify.ndyzhhqj --schema-only

docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/tools:/app/tools:ro" \
  --entrypoint python chameleon-engine -m unittest discover -s tests -v

docker run --rm --platform linux/amd64 --network none \
  --entrypoint python chameleon-engine -m pip check
```

All commands exited 0. Full stdout/stderr are saved as `build.log`, `run-1.log`,
`run-2.log`, `audit.log`, `schema.log`, `tests.log`, and `pip-check.log` in the
checkpoint artifact directory. The rebuilt distribution inventory is recorded
by the audit in `verification.json`; exact comparison with the previous inventory,
constraints, and saved JSON/PNG bytes passed separately.

### Remaining limitations and proposed checkpoint

Output behavior is unchanged: the dense Level 3 banner still has a 13 px
headline, 9 px body/group text, and difficult-to-read 7 px legal text. The
intentional missing asset remains the real renderer's labeled placeholder.
Its actual pixels, including that placeholder, are identical to the inspected
previous verification. Original sample content was not edited. Hidden inputs,
official scoring, and the separate viewer are not verified by these local checks.

See [checkpoint proposal](checkpoint.md) for the exact files proposed for a
commit, including the existing uncommitted engine implementation and tests.
No commit or push was performed.

---

## Initial verification — 2026-10-25

**Passed on 2026-10-25: the supplied Linux/amd64 image builds and runs the three
original samples offline.** Both normal runs and the fail-closed renderer audit
passed. All 28 existing regression tests passed inside the image. No packaging
fix, runtime/layout change, renderer modification, commit, or push was needed.

The earlier unavailable-Docker result is superseded by this completed run.
Docker required access outside the workspace sandbox; authorized daemon access
succeeded. No host Docker configuration was changed.

## Evidence and environment

Artifacts are in [`artifacts/submission-verify.m8m36wud/`](../artifacts/submission-verify.m8m36wud/).
`artifacts/submission-latest.txt` now points to the newer checkpoint run above. Existing `output/`
and visual-comparison artifacts were not used as verification outputs or changed.

- Docker client/server: 29.9.2; Docker Desktop 4.96.3 (244472).
- Host daemon: Linux/aarch64 on this ARM Mac; image and execution: Linux/amd64,
  with Python reporting `x86_64` (Docker Desktop's architecture emulation).
- Image ID: `sha256:589aed83d84fa1e8173f55b1a48827fa7e67f005403ec3c0d738eef59a6d25c0`.
- Base image: `python:3.11-slim`, resolved manifest
  `sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377`.
- Python 3.11.17; Pillow 13.0.0; skia-python 144.1; NumPy 2.4.6;
  cr-renderer 0.1.0, Git commit `a17e1fb9a732959dd6c21ae168d5ee09d74bd64f`.
- Independent host schema validator: jsonschema 4.26.0, Draft 2020-12.

Full versions, image configuration, and resolved Python packages are recorded in
[`docker-version.txt`](../artifacts/submission-verify.m8m36wud/docker-version.txt),
[`image-inspect.json`](../artifacts/submission-verify.m8m36wud/image-inspect.json), and
[`verification.json`](../artifacts/submission-verify.m8m36wud/verification.json).

## Commands actually executed

Working directory: `/Users/vedu/chameleon`. The build used the supplied
Dockerfile and requirements unchanged:

```sh
docker version
docker info --format '{{.OSType}}/{{.Architecture}}'
docker build --platform linux/amd64 -t chameleon-engine .
docker image inspect chameleon-engine
```

A fresh directory was allocated with Python's `tempfile.mkdtemp`, followed by
empty `run-1`, `run-2`, `audit`, and `direct` subdirectories. The setup also wrote
SHA-256 hashes for all source inputs, runtime modules, renderer files, brand
assets/fonts, schema, Dockerfile, and requirements. The equivalent reproducible
setup below is the code used (rerunning it creates a **new** directory):

```sh
python - <<'PY'
import tempfile, json, hashlib
from pathlib import Path
root = Path.cwd()
base = root / 'artifacts'
base.mkdir(exist_ok=True)
run = Path(tempfile.mkdtemp(prefix='submission-verify.', dir=base))
for name in ('run-1', 'run-2', 'audit', 'direct'):
    (run / name).mkdir()
paths = [p for d in ('engine', 'renderer', 'brand_kit', 'input')
         for p in (root / d).rglob('*')
         if p.is_file() and '__pycache__' not in p.parts]
paths += [root / 'Dockerfile', root / 'requirements.txt',
          root / 'chameleon_design_schema_v0.9.json']
(run / 'source-hashes.json').write_text(json.dumps({
    str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in paths}, indent=2))
(base / 'submission-latest.txt').write_text(str(run) + '\n')
print(run)
PY
```

The two normal entrypoint commands, with the actual fresh output paths, were:

```sh
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/artifacts/submission-verify.m8m36wud/run-1:/app/output" \
  chameleon-engine

docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/artifacts/submission-verify.m8m36wud/run-2:/app/output" \
  chameleon-engine
```

Verification and regression commands:

```sh
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/tools:/app/tools:ro" \
  -v "$PWD/artifacts/submission-verify.m8m36wud:/verification" \
  --entrypoint python chameleon-engine \
  -m tools.verify_submission /verification

python -m tools.verify_submission artifacts/submission-verify.m8m36wud --schema-only

docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/tests:/app/tests:ro" \
  -v "$PWD/tools:/app/tools:ro" \
  --entrypoint python chameleon-engine -m unittest discover -s tests -v

docker run --rm --platform linux/amd64 --network none \
  --entrypoint python chameleon-engine -m pip check
```

All commands above exited **0**. Build, normal runs, audit, schema validation,
tests, and dependency checks captured stdout/stderr separately in `build.log`,
`run-1.log`, `run-2.log`, `audit.log`, `schema.log`, `tests.log`, and `pip-check.log`.
Use a newly allocated directory and substitute its path throughout for another
verification. The audit intentionally refuses to reuse nonempty `audit/` or
`direct/` directories. It does not install development dependencies into the
submission image; independent jsonschema validation runs on the host.

## Actual acceptance results

| Check | Result |
| --- | --- |
| Supplied Dockerfile builds for Linux/amd64 | PASS; no packaging changes |
| Fresh output set for each normal run | PASS; exactly 3 JSON + 3 PNG files |
| Real renderer, no orchestrator fallback | PASS; 3 recorded real-renderer calls with fallback forbidden; all normal/audit PNG pixels equal direct real-renderer PNGs |
| Exact IDs and multiplicities | PASS; 4, 11, and 17 elements; every source ID exactly once |
| Content, font families, style runs, asset references, groups, other protected fields | PASS; deep comparison permits only geometry and text font-size changes |
| Foreground image box proportions | PASS; relative tolerance 1e-9 |
| Schema validity | PASS; engine schema checks plus independent Draft 2020-12 validation of 3 sources and all 9 normal/audit output JSONs |
| Structural, group, rotated box/ink bounds, typography and collision checks | PASS; zero hard errors, text overflows, or unintended collisions for all 3 samples |
| Deterministic JSON | PASS; parsed objects and file bytes identical across both normal runs and audited third run |
| Offline runtime | PASS; all execution/audit/test containers ran with `--network none`, original inputs mounted read-only, no runtime downloads or installs required |
| Source input immutability | PASS; audited resize calls compare nested source/target data before and after |
| Working tree preservation | PASS; all 39 pre-build hashed files unchanged, including complete engine, renderer, brand kit, original inputs, schema, Dockerfile, requirements |
| Existing regressions in image | PASS; 28 tests in 8.019 seconds |
| Installed dependency consistency | PASS; `pip check`: `No broken requirements found.` |

The development-only harness is [tools/verify_submission.py](../tools/verify_submission.py).
It patches `_fallback_render` **in memory only** to raise, records converter
calls, then rerenders saved designs directly through the supplied converter.
It checks PNG decoding, exact target dimensions, and RGBA pixel equality.
Neither `main.py` nor any renderer file was edited. Tests cover long text,
rotations, explicit/inferred groups, renamed IDs, shuffled input, additional
compositions, real assets, and preservation of the visual-quality improvements.
Local quality checks remain heuristic, not official scoring.

Machine-readable findings:
[`verification.json`](../artifacts/submission-verify.m8m36wud/verification.json),
[`schema-verification.json`](../artifacts/submission-verify.m8m36wud/schema-verification.json),
[`preservation.json`](../artifacts/submission-verify.m8m36wud/preservation.json).

## Rendered inspection and remaining limitations

All three fresh Docker PNGs were opened and inspected:

| Sample | PNG | Actual Docker measurements |
| --- | --- | --- |
| Level 1 | [1080 × 1350](../artifacts/submission-verify.m8m36wud/run-1/chameleon_sample_level1_warmup_output.png) | Headline 60 px, CTA 30 px; logo box 320 × 100 px |
| Level 2 | [1600 × 400](../artifacts/submission-verify.m8m36wud/run-1/chameleon_sample_level2_core_output.png) | Headline 44.8 px, subheading 19.2 px; text box gap 11.2 px, measured ink gap 16.36 px; product box 245.66 × 245.66 px |
| Level 3 | [728 × 90](../artifacts/submission-verify.m8m36wud/run-1/chameleon_sample_level3_advanced_output.png) | Headline 13 px, subheading/button/ribbon labels 9 px, legal 7 px; product box 74.65 × 74.65 px; logo 69.63 × 21.76 px |

Level 2 retains a coherent headline/subheading block. Level 3 retains headline
prominence and recognizable product art, but remains very dense. Its 7 px legal
text is difficult to read at native size; the small logo and tight badge row
remain visual compromises. Passing structural checks does not make this banner
fully readable or establish an official score.

The real renderer reports exactly the intentional Level 3 missing asset:
`solstice_holiday_badge_2025.png` on `holiday_watermark`. The element/reference is
preserved, and its labeled placeholder remains visually awkward. This is the
supplied renderer's missing-asset behavior, **not** the orchestrator fallback.
No asset was invented or replaced.

There were no build or dependency failures. Nonfatal warnings observed:

- Docker's `FromPlatformFlagConstDisallowed` lint warning for the supplied
  `FROM --platform=linux/amd64` line; retained unchanged as requested.
- Debian package setup used noninteractive debconf; pip warned about root
  installation in the build image and advertised a newer pip version.
- Runtime Fontconfig warned that `05-reset-dirs-sample.conf` contains an unknown
  `reset-dirs` element. Rendering, font measurement, pixel comparisons, and
  regression checks still passed; no official font/renderer files were changed.
- The intentional invalid-font regression emitted its expected font fallback
  messages; those are distinct from an orchestrator renderer fallback.

At this initial verification, dependencies and the base image were unpinned.
The 2026-10-26 checkpoint above supersedes that limitation for Python package
versions, the renderer revision, and the base image digest.
This verifies the recorded image, not that future fresh builds resolve identical
packages. Build-time internet access was used for the base image, apt, and pip;
runtime offline execution was verified separately. The Linux environment has
different font measurements/output from the earlier native report (for example,
9 px body/group text here versus 8 px previously); no runtime code changed.
Determinism is established within this image, not across platforms/dependency
versions. This was amd64 execution under ARM-host emulation, not a native amd64
hardware benchmark. Hidden challenge inputs, official judging, and the separate
viewer/submission process were not verified in this pass.
