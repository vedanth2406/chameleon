"""Development-only container audit; never installed into the runtime image.

Run after two normal entrypoint runs. See docs/submission-verification.md
for read-only mounts, network isolation, and independent host schema validation.
Failures raise immediately; a report is written only after all checks pass.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
from unittest.mock import patch


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tasks():
    paths = sorted(Path('input').glob('*.json'))
    require(paths, 'No original sample tasks found')
    return [(p.stem, json.loads(p.read_text())) for p in paths]


def schema_audit(directory):
    # Deliberately independent of the engine's schema implementation.
    from jsonschema import Draft202012Validator
    schema = json.loads(Path('chameleon_design_schema_v0.9.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    checked = []
    for stem, task in tasks():
        validator.validate(task['source'])
        for run in ('run-1', 'run-2', 'audit'):
            path = directory / run / f'{stem}_output.json'
            validator.validate(json.loads(path.read_text()))
            checked.append(str(path))
    return dict(validator='jsonschema.Draft202012Validator',
                version=importlib.metadata.version('jsonschema'),
                source_count=len(tasks()), output_count=len(checked), checked=checked)


def container_audit(directory):
    from PIL import Image
    from engine import main
    from engine.analysis import analyze
    from engine.geometry import inside
    from engine.quality import evaluate
    from engine.validation import schema_errors
    from renderer.converter import convert
    from tools.evaluate import design_metrics

    original_tasks = tasks()
    expected = {f'{stem}_output.{suffix}' for stem, _ in original_tasks
                for suffix in ('json', 'png')}
    for run in ('run-1', 'run-2'):
        require({p.name for p in (directory/run).iterdir()} == expected,
                f'{run}: missing or unexpected output files')
    for name in ('audit', 'direct'):
        require(not any((directory/name).iterdir()), f'{name} must be empty')

    manifest = json.loads((directory/'source-hashes.json').read_text())
    for name, sha in manifest.items():
        # Dockerfile/requirements are build inputs, not installed at these paths.
        if name == 'Dockerfile':
            continue
        path = Path(name)
        require(path.is_file() and digest(path) == sha, f'Image/input differs: {name}')

    calls, immutable_calls = [], []
    real_render, real_resize = convert.render_design_to_png, main.resize

    def recorded_render(design, assets_dir, png_path, *args, **kwargs):
        result = real_render(design, assets_dir, png_path, *args, **kwargs)
        calls.append(Path(png_path).name)
        return result

    def immutable_resize(source, target):
        before = deepcopy((source, target))
        result = real_resize(source, target)
        require((source, target) == before, 'resize mutated its input')
        immutable_calls.append(True)
        return result

    def forbidden_fallback(*args, **kwargs):
        raise AssertionError('Orchestrator fallback renderer invoked')

    with patch.object(main, 'OUTPUT_DIR', directory/'audit'), \
            patch.object(main, '_fallback_render', forbidden_fallback), \
            patch.object(main, 'resize', immutable_resize), \
            patch.object(convert, 'render_design_to_png', recorded_render):
        require(main.main() == 0, 'Audited entrypoint failed')
    require(Counter(calls) == Counter(f'{s}_output.png' for s, _ in original_tasks),
            'Real renderer did not render every task exactly once')
    require(len(immutable_calls) == len(original_tasks), 'Missing immutability checks')
    require({p.name for p in (directory/'audit').iterdir()} == expected,
            'Audit output set differs')

    records = []
    for stem, task in original_tasks:
        source, target = task['source'], task['target_canvas']
        analysis = analyze(source)
        path = directory/'run-1'/f'{stem}_output.json'
        design = json.loads(path.read_text())
        require(design['canvas'] == target, f'{stem}: target mismatch')
        require(not schema_errors(design), f'{stem}: engine schema errors')
        require(not main.self_check(source, design), f'{stem}: self-check errors')
        require(Counter(e['id'] for e in design['elements']) ==
                Counter(e['id'] for e in source['elements']), f'{stem}: ID multiplicities')
        require(all(n == 1 for n in Counter(e['id'] for e in design['elements']).values()),
                f'{stem}: duplicate IDs')
        original = {e['id']: e for e in source['elements']}
        for e in design['elements']:
            old = original[e['id']]
            mutable = {'x', 'y', 'width', 'height'}
            if old['type'] == 'text':
                mutable.add('font_size')
            require({k: v for k, v in old.items() if k not in mutable} ==
                    {k: v for k, v in e.items() if k not in mutable},
                    f'{stem}/{e["id"]}: protected content/style/group/asset changed')
            require(e['width'] > 0 and e['height'] > 0 and inside(e, target),
                    f'{stem}/{e["id"]}: nonpositive box or rotated clipping')
            if e['type'] == 'image' and e['id'] not in analysis['background_ids']:
                require(math.isclose(e['width']/e['height'], old['width']/old['height'],
                                     rel_tol=1e-9), f'{stem}/{e["id"]}: image proportion')
        quality = evaluate(source, design, analysis)
        require(not quality['hard_errors'], f'{stem}: {quality["hard_errors"]}')
        png_name = f'{stem}_output.png'
        direct = directory/'direct'/png_name
        warnings = real_render(design, main.ASSETS_DIR, direct)
        with Image.open(direct) as img:
            img.load()
            require(img.format == 'PNG', f'{stem}: invalid direct PNG')
            require(img.size == (target['width'], target['height']), f'{stem}: PNG size')
            pixels = img.convert('RGBA').tobytes()
        for run in ('run-1', 'run-2', 'audit'):
            output = directory/run/path.name
            require(json.loads(output.read_text()) == design, f'{stem}: JSON differs in {run}')
            require(output.read_bytes() == path.read_bytes(), f'{stem}: JSON bytes differ in {run}')
            with Image.open(directory/run/png_name) as img:
                img.load()
                require(img.format == 'PNG' and img.size == (target['width'], target['height'])
                        and img.convert('RGBA').tobytes() == pixels,
                        f'{stem}/{run}: PNG differs from direct real renderer')
        record = design_metrics(source, design, analysis, quality, warnings)
        record.update(name=stem, element_count=len(design['elements']),
                      json_sha256=digest(path), png_sha256=digest(direct),
                      json_bytes_equal=True, real_renderer_pixels_equal=True)
        records.append(record)
    return dict(python=platform.python_version(), machine=platform.machine(),
                network_interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir()),
                packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
                renderer_origin=json.loads(importlib.metadata.distribution('cr-renderer').read_text('direct_url.json')),
                real_renderer_calls=calls, input_immutability_checks=len(immutable_calls),
                samples=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--schema-only', action='store_true')
    args = parser.parse_args()
    result = schema_audit(args.directory) if args.schema_only else container_audit(args.directory)
    filename = 'schema-verification.json' if args.schema_only else 'verification.json'
    (args.directory/filename).write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: {filename}', flush=True)


if __name__ == '__main__':
    main()
