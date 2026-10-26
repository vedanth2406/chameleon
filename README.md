# CHAMELEON layout engine

An offline, deterministic design-resizing engine. The public interface is
`resize(source: dict, target_canvas: dict) -> dict` in `engine/resize.py`.
`engine.main` reads tasks from `input/` and writes one resized JSON and one
real-renderer PNG per task to `output/`.

## Build and run

Docker with Linux/amd64 support is the verified runtime. Build-time internet
access is required; runtime works with networking disabled.

```sh
docker build --platform linux/amd64 -t chameleon-engine .
mkdir -p artifacts
chameleon_run_dir=$(mktemp -d "$PWD/artifacts/run.XXXXXX")
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$chameleon_run_dir:/app/output" \
  chameleon-engine
```

Open the `_output.png` and `_output.json` files in `$chameleon_run_dir`
(print the path with `echo "$chameleon_run_dir"`). A fresh directory prevents stale outputs
from masking failures. The three original sample tasks are included.

`requirements.txt` pins Pillow and the exact cr-renderer Git commit.
`constraints-linux-amd64.txt` pins the verified container's transitive Python
packages; it is consumed by both pip and Docker. The base image is pinned by
digest. These versions came from the verified Linux image, not a Mac Conda
package export. System packages installed by apt and isolated Python build
backends are not fully locked; this is a version checkpoint, not a byte-for-byte
image rebuild guarantee.

For local iteration, use a separate Python 3.11 environment with compatible
system libraries (the Docker image remains the reproducibility reference):

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m engine.main
```

## Approach and guarantees

The engine infers backgrounds, decoration, importance, and related layout units;
explicit groups take precedence. It generates several arrangements, measures
and wraps text with the supplied fonts and renderer helpers, checks and repairs
candidates, then selects a layout deterministically. Scoring considers readable
text, hierarchy, recognizable foreground imagery, composition, spacing,
collisions, and rotated bounds. Similar aspect ratios favor source composition.

Every element ID, text string, font family, style run, asset reference, and group
membership is preserved. Only permitted geometry and text font-size changes are
made; inputs are not mutated. Foreground image boxes retain their proportions.
No content is hidden, deleted, regenerated, or replaced. Runtime uses local
assets/fonts and requires no API calls or model downloads.

Runtime helpers live in `engine/`. The supplied `engine/main.py`, renderer,
brand kit, schema, and original samples remain unchanged. Development tools and
tests are separate and excluded from the Docker build context.

## Verification and development

Run the existing suite against the built image without installing test tools
into the runtime image:

```sh
docker run --rm --platform linux/amd64 --network none \
  -v "$PWD/input:/app/input:ro" \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/tools:/app/tools:ro" \
  --entrypoint python chameleon-engine -m unittest discover -s tests -v
```

In a local development environment, generate comparisons with the real renderer:

```sh
python -m tools.evaluate --synthetic --wide all
```

Open `artifacts/comparisons/index.html` for source, stretch baseline, and selected
layouts with PNGs, JSON, and measurements. Generated artifacts and comparison
archives are ignored by Git. See [submission verification](docs/submission-verification.md)
for actual build/run results, independent schema validation, fail-closed renderer
checks, dependency provenance, and exact repeat-run commands.

## Known limitations

- Dense or extreme targets can still need very small text. The verified Level 3
  banner has a 13 px headline, 9 px body/group text, and 7 px legal text; the legal
  text remains difficult to read. Impossible fits emit warnings and preserve
  content rather than silently removing it.
- Group/role/overlap inference and local scores are heuristics, not official
  scoring. Hidden inputs and the separate viewer submission are not verified.
- The intentional missing Level 3 asset remains a labeled placeholder from the
  real renderer. It is not repaired or replaced.
- The supplied orchestrator can fall back to a box/label renderer on import
  failure, and self-check warnings do not fail its exit code. The verification
  harness explicitly rejects that fallback and validates the saved outputs.
- Font measurement and rasterization can differ across platforms and dependency
  versions. Determinism is verified within the pinned Linux image.

See [the internal contract](docs/team-contract.md),
[development notes](docs/development.md), [visual findings](docs/visual-quality.md),
[RULES.md](RULES.md), [FAQ.md](FAQ.md), and the
[design schema](chameleon_design_schema_v0.9.json).
