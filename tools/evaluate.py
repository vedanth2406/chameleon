"""Real-renderer comparisons. Run: python -m tools.evaluate --synthetic

No fallback renderer is accepted. Artifacts stay outside input/ and output/.
Network connections are blocked during generation and rendering.
"""
import argparse
from copy import deepcopy
import html
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch
import warnings

from engine.analysis import analyze
from engine.layout import generate_candidates
from engine.quality import evaluate
from engine.resize import resize
from engine.typography import measure_text
from engine.relationships import text_links
from renderer.converter.convert import render_design_to_png
from tools.baseline import stretch

ROOT = Path(__file__).resolve().parents[1]


def cases(include_synthetic, wide_split=None):
    result = [(p.stem, json.loads(p.read_text())) for p in sorted((ROOT/'input').glob('*.json'))]
    if include_synthetic:
        from tests.test_engine import composition
        for name, n, target in (
                ('synthetic-portrait', 2, (420, 900)),
                ('synthetic-square', 4, (720, 720)),
                ('synthetic-landscape', 6, (1100, 430)),
                ('synthetic-extreme', 4, (1200, 160))):
            result.append((name, dict(source=composition(n, rotation=17),
                                     target_canvas=dict(zip(('width','height'),target)))))
    if wide_split:
        from tools.quality_cases import wide_cases
        splits = ('tuning', 'real-controls', 'holdout') if wide_split == 'all' else (wide_split,)
        for split in splits:
            result.extend(wide_cases(split))
    return result


def design_metrics(source, design, analysis, quality, render_warnings):
    fonts, images, gaps = [], [], []
    by_id = {e['id']: e for e in design['elements']}
    for e in design['elements']:
        if e['type'] == 'text':
            m = measure_text(e)
            fonts.append(dict(id=e['id'], font_size=e['font_size'], rendered_font_size=int(e['font_size']),
                              width=e['width'], height=e['height'], line_count=m['line_count'],
                              overflow_x=m['overflow_x'], overflow_y=m['overflow_y']))
        elif e['type'] == 'image' and e['id'] not in analysis['background_ids']:
            images.append(dict(id=e['id'],asset_id=e['asset_id'],width=e['width'],height=e['height'],
                               existing_asset=(ROOT/'brand_kit'/'assets'/e['asset_id']).is_file()))
    for aid, bid in text_links(source,analysis):
        if aid not in by_id or bid not in by_id: continue
        a,b=by_id[aid],by_id[bid]
        ma,mb=measure_text(a),measure_text(b)
        gaps.append(dict(ids=[aid,bid],box_gap=b['y']-a['y']-a['height'],
                         ink_gap=b['y']+mb['ink_bounds'][1]-a['y']-ma['ink_bounds'][1]-ma['ink_bounds'][3]))
    return dict(evaluation=quality,render_warnings=render_warnings,
                min_font_size=min((f['font_size'] for f in fonts),default=None),fonts=fonts,images=images,text_gaps=gaps,
                overflows=[f['id'] for f in fonts if f['overflow_x'] or f['overflow_y']],
                collisions=[e for e in quality['hard_errors'] if 'unintended overlap' in e])


def build_report(destination, include_synthetic=False, before_dir=None, wide_split=None):
    destination = Path(destination).resolve()
    for protected in (ROOT/'input', ROOT/'output'):
        if destination == protected or protected in destination.parents:
            raise ValueError('Comparison artifacts must be outside official input/output directories')
    destination.mkdir(parents=True, exist_ok=True)
    sections, records = [], []
    with patch.object(socket.socket, 'connect', side_effect=RuntimeError('Network is disabled during evaluation')):
        for name, task in cases(include_synthetic, wide_split):
            source, target = task['source'], task['target_canvas']
            before = deepcopy(task)
            analysis = analyze(source)
            start = time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                improved = resize(source, target)
            elapsed = time.perf_counter() - start
            candidates = generate_candidates(source, target, analysis)
            record = dict(name=name, seconds=elapsed, candidate_count=len(candidates),
                          diagnostics=analysis['diagnostics'], warnings=[str(w.message) for w in caught], designs={})
            panels = []
            variants = [('source', source), ('baseline', stretch(source, target))]
            if before_dir is not None:
                before_dir = Path(before_dir)
                frozen_task = json.loads((before_dir/f'{name}-task.json').read_text())
                if frozen_task != task:
                    raise ValueError(f'Before/after inputs differ for {name}')
                variants.append(('before', json.loads((before_dir/f'{name}-design.json').read_text())))
            variants.append(('improved', improved))
            for label, design in variants:
                stem = f'{name}-{label}'
                png = destination / f'{stem}.png'
                render_warnings = render_design_to_png(design, ROOT/'brand_kit'/'assets', png,
                                                       max_size=max(design['canvas'].values()))
                (destination/f'{stem}.json').write_text(json.dumps(design, indent=2))
                quality = evaluate(source, design, analysis)
                record['designs'][label] = design_metrics(source, design, analysis, quality, render_warnings)
                details = html.escape(json.dumps(record['designs'][label], indent=2))
                width, height = design['canvas']['width'], design['canvas']['height']
                measured = record['designs'][label]
                badge = f"{len(quality['hard_errors'])} hard errors · {len(measured['overflows'])} text overflows · {len(measured['collisions'])} collisions · score {quality['score']:.2f}"
                rows = ''.join(f"<tr><td>{html.escape(f['id'])}</td><td>{f['font_size']:.2f} / {f['rendered_font_size']}</td><td>{f['line_count']}</td></tr>" for f in measured['fonts'])
                image_rows = ''.join(f"<tr><td>{html.escape(i['id'])}</td><td>{i['width']:.1f} × {i['height']:.1f}</td><td>{'Real asset' if i['existing_asset'] else 'Missing asset'}</td></tr>" for i in measured['images'])
                tables = f'<details><summary>Actual fonts and image boxes</summary><table><tr><th>Text</th><th>Size / rendered px</th><th>Lines</th></tr>{rows}</table><table><tr><th>Image</th><th>Box px</th><th>Asset</th></tr>{image_rows}</table></details>'
                panels.append(f'<article><h3>{label.title()} <small>{width} × {height}</small></h3>'
                              f'<a href="{stem}.png"><img src="{stem}.png" alt="{html.escape(name)} {label}"></a>'
                              f'<p>{badge}</p>{tables}<details><summary>Measurements and warnings</summary><pre>{details}</pre></details>'
                              f'<p><a href="{stem}.json">Design JSON</a> · <a href="{stem}.png">Full-size PNG</a></p></article>')
            assert task == before, 'Evaluation must not mutate inputs'
            records.append(record)
            sections.append(f'<section><h2>{html.escape(name)}</h2><p>{len(candidates)} candidates · {elapsed:.3f} s resize</p>'
                            f'<div class="comparisons">{"".join(panels)}</div></section>')
            print(name, 'errors:', len(record['designs']['improved']['evaluation']['hard_errors']), 'min font:', record['designs']['improved']['min_font_size'], flush=True)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CHAMELEON — local comparisons</title><style>
body{margin:0;padding:32px;font:16px/1.5 system-ui;background:#16151b;color:#eee}a{color:#b9b2ff}
table{border-collapse:collapse;font-size:13px;width:100%;margin:12px 0}td,th{text-align:left;padding:6px;border-bottom:1px solid #555}h1,h2,h3{line-height:1.2}small{font-size:13px;color:#aaa}section{margin:40px 0;border-top:1px solid #555;padding-top:20px}
.comparisons{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:#24222c;padding:16px;border-radius:10px}
img{display:block;max-width:100%;max-height:500px;object-fit:contain;object-position:left top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
@media(max-width:1000px){.comparisons{grid-template-columns:1fr}}p{max-width:100ch}
</style><h1>CHAMELEON local comparisons</h1>
<p>All PNGs use the supplied converter and cr-renderer with local fonts/assets and network connections blocked.
Click a PNG for inspection at full resolution. These scores are local heuristics, not official challenge scores.
A missing-asset placeholder is produced by the real renderer; no asset is replaced by the engine.
The Before panel is the previous working engine, captured before tuning; Baseline is the original stretch. Scores for all panels use the current heuristic. Zero hard errors does not guarantee readable or attractive output. Inspect small fonts and composition. Fixtures named reserved were evaluated only after tuning was frozen; real-controls use existing assets only.</p>
'''+''.join(sections)+'</html>'
    (destination/'index.html').write_text(page)
    (destination/'metrics.json').write_text(json.dumps(records, indent=2))
    print(f'Report: {destination / "index.html"}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts'/'comparisons')
    parser.add_argument('--synthetic',action='store_true')
    parser.add_argument('--before-dir',type=Path,help='Directory of frozen NAME-task.json / NAME-design.json pairs')
    parser.add_argument('--wide',choices=['tuning','real-controls','holdout','all'])
    args=parser.parse_args()
    build_report(args.out,args.synthetic,args.before_dir,args.wide)


if __name__ == '__main__':
    main()
