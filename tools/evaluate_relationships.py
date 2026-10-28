"""Render frozen-before/current-after relationship probes without editing assets.

Requires an existing pre-change engine snapshot and a completed 24-task rerun.
All outputs remain under artifacts/. Local scores are not official scores.
"""
import argparse
from copy import deepcopy
import html
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from unittest.mock import patch

from engine.analysis import analyze
from engine.resize import resize
from tools.generalization import ROOT, metrics, page, panel, render, save
from tools.relationship_cases import compositions


WORKER = r'''
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
from engine.resize import resize
from renderer.converter.convert import render_design_to_png
tasks = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
with patch.object(socket.socket, 'connect', side_effect=RuntimeError('Network disabled')):
    for task in tasks:
        design = resize(task['source'], task['target_canvas'])
        path = out / (task['name']+'-output')
        path.with_suffix('.json').write_text(json.dumps(design, indent=2)+'\n')
        render_design_to_png(design, Path('brand_kit/assets'), path.with_suffix('.png'),
                             max_size=max(design['canvas'].values()))
'''


def compare(before, after, root, old_suite, new_suite):
    rows = []
    for old, new in zip(before, after):
        assert old['name'] == new['name']
        name = old['name']; om, nm = old['metrics'], new['metrics']
        changed = json.loads((old_suite/(name+'-output.json')).read_text()) != json.loads((new_suite/(name+'-output.json')).read_text())
        pixels_changed = (old_suite/(name+'-output.png')).read_bytes() != (new_suite/(name+'-output.png')).read_bytes()
        row = dict(name=name, design_changed=changed, png_bytes_changed=pixels_changed)
        for key in ('lost_containment', 'lost_intended_layers', 'overflows', 'semantic_collisions',
                    'preservation_errors', 'schema_errors', 'bounds_errors', 'group_errors'):
            row[key] = [len(om[key]), len(nm[key])]
        row['min_font_size'] = [om['min_font_size'], nm['min_font_size']]
        row['images'] = [om['images'], nm['images']]
        rows.append(row)
    save(root/'suite-delta.json', rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before-engine', type=Path, required=True)
    p.add_argument('--before-suite', type=Path, required=True)
    p.add_argument('--after-suite', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    assert out.is_relative_to(ROOT/'artifacts')
    review = json.loads((out/'review.json').read_text()) if (out/'review.json').exists() else {}
    old_suite, new_suite = args.before_suite.resolve(), args.after_suite.resolve()
    fixtures = compositions(); tasks = []
    for f in fixtures:
        for i, target in enumerate(f['targets'], 1):
            tasks.append(dict(name=f['name']+f'-t{i}', source=f['source'], target_canvas=target))
    for path in sorted((ROOT/'input').glob('*.json')):
        tasks.append(dict(name=path.stem, **json.loads(path.read_text())))
    save(out/'tasks.json', tasks)
    for name in ('before', 'after'): (out/name).mkdir(exist_ok=True)
    frozen = out/'frozen-runtime'; frozen.mkdir(exist_ok=True)
    if not (frozen/'engine').exists(): shutil.copytree(args.before_engine, frozen/'engine')
    for name in ('renderer', 'brand_kit', 'chameleon_design_schema_v0.9.json'):
        if not (frozen/name).exists(): (frozen/name).symlink_to(ROOT/name)
    source_metrics = {}
    for f in fixtures:
        m = metrics(f, f['source'])
        assert not m['schema_errors'] and not m['overflows'] and not m['bounds_errors']
        if not f['adversarial']: assert not m['semantic_collisions']
        stem = f['name']+'-source'; save(out/(stem+'.json'), f['source'])
        m['render_warnings'] = render(f['source'], out/(stem+'.png'))
        source_metrics[f['name']] = m
    subprocess.run([sys.executable, '-c', WORKER, str(out/'tasks.json'), str(out/'before')],
                   cwd=frozen, env={**os.environ, 'PYTHONPATH': str(frozen)}, check=True)
    summaries = []; body = '<p>Frozen pre-change engine versus relationship-aware engine. Native-size previews; scroll to inspect. No official scoring.</p>'
    with patch.object(socket.socket, 'connect', side_effect=RuntimeError('Network disabled')):
        for f in fixtures:
            m = source_metrics[f['name']]; stem = f['name']+'-source'
            body += '<section><h2>'+f['name']+'</h2><p>'+html.escape(f['description'])+'</p>'+panel(stem, 'Source', m)
            for i, target in enumerate(f['targets'], 1):
                name = f['name']+f'-t{i}'; src = deepcopy(f['source'])
                result = resize(src, target); assert src == f['source']
                assert result == resize(src, target), 'Nondeterministic design JSON'
                save(out/'after'/(name+'-output.json'), result)
                notes = render(result, out/'after'/(name+'-output.png'))
                old = json.loads((out/'before'/(name+'-output.json')).read_text())
                om, nm = metrics(f, old), metrics(f, result, render_warnings=notes)
                for key in ('schema_errors', 'preservation_errors', 'bounds_errors', 'group_errors', 'overflows'):
                    assert not nm[key], (name, key, nm[key])
                assert not nm['evaluation']['hard_errors']
                # Re-score before outputs with CURRENT evaluator to expose costs
                # previously absent; old selection scores live in the old suite.
                summaries.append(dict(name=name, before=om, after=nm, analysis=analyze(src)))
                body += '<p><strong>Visual review:</strong> '+html.escape(review.get(name, 'Pending'))+'</p>'
                body += panel('before/'+name+'-output', 'Before (re-scored by current evaluator)', om)
                body += panel('after/'+name+'-output', 'After', nm)
            body += '</section>'
        sample_checks = []
        for task in tasks[len(fixtures)*2:]:
            result = resize(task['source'], task['target_canvas'])
            name = task['name']; save(out/'after'/(name+'-output.json'), result)
            render(result, out/'after'/(name+'-output.png'))
            same = result == json.loads((out/'before'/(name+'-output.json')).read_text())
            png_same = (out/'before'/(name+'-output.png')).read_bytes() == (out/'after'/(name+'-output.png')).read_bytes()
            assert same and png_same, name+' original sample changed'
            sample_checks.append(dict(name=name, json_identical=same, png_identical=png_same))
    save(out/'new-probe-metrics.json', summaries); save(out/'original-sample-checks.json', sample_checks)
    (out/'new-probes.html').write_text(page('Additional relationship controls', body))
    old_records = json.loads((old_suite/'metrics.json').read_text()); new_records = json.loads((new_suite/'metrics.json').read_text())
    deltas = compare(old_records, new_records, out, old_suite, new_suite)
    body = '<p>All 24 outputs re-evaluated. <a href="new-probes.html">Eight additional controls and source previews</a> · <a href="suite-delta.json">All changes</a></p>'
    for old, new, delta in zip(old_records, new_records, deltas):
        name = old['name']; body += '<section><h2>'+name+(' — changed' if delta['design_changed'] else ' — unchanged')+'</h2>'
        body += '<p><strong>Visual review:</strong> '+html.escape(review.get(name, 'Pending'))+'</p>'
        body += panel(os.path.relpath(old_suite/(name+'-output'), out), 'Before (old evaluator)', old['metrics'])
        body += panel(os.path.relpath(new_suite/(name+'-output'), out), 'After', new['metrics'])+'</section>'
    (out/'index.html').write_text(page('Relationship preservation: before and after', body))
    print(json.dumps(dict(changed=[r['name'] for r in deltas if r['design_changed']], samples=sample_checks), indent=2))


if __name__ == '__main__': main()
