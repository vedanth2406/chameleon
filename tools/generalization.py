"""Separate, staged generalization evaluation. Never tunes or edits the engine.

sources: validate fixtures and render sources ONLY. Inspect before using run.
run: require reviewed-source hashes; evaluate 24 tasks and export candidates.
report: rebuild HTML after adding human observations in review.json.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import html
import importlib.metadata
from itertools import combinations
import json
import math
from pathlib import Path
import platform
import socket
import subprocess
from unittest.mock import patch
import warnings

from PIL import Image
from engine.analysis import analyze
from engine.geometry import bounds, inside, ink_box, polygon_overlap
from engine.layout import generate_candidates
from engine.quality import evaluate, repair
from engine.resize import resize
from engine.typography import measure_text
from engine.validation import schema_errors
from renderer.converter.convert import render_design_to_png
from renderer.converter.assets import load_asset_image
from tools.generalization_cases import compositions
from tools.evaluate import design_metrics

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'brand_kit/assets'


def save(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def ignored_pair(a, b, intent):
    ignored = set(intent['backgrounds']+intent['decorative'])
    return (a['id'] in ignored or b['id'] in ignored or
            sorted((a['id'], b['id'])) in [list(p) for p in intent['overlap_pairs']])


def semantic_collisions(design, intent):
    result=[]
    for a,b in combinations(design['elements'],2):
        if ignored_pair(a,b,intent):continue
        fraction=polygon_overlap(a,b)/max(1e-9,min(a['width']*a['height'],b['width']*b['height']))
        if fraction>.015:result.append(dict(ids=[a['id'],b['id']],fraction=fraction))
    return result


def preserved(source, result):
    errors=[]
    if Counter(e['id'] for e in source['elements']) != Counter(e['id'] for e in result['elements']):
        errors.append('ID multiplicities differ')
    original={e['id']:e for e in source['elements']}
    for e in result['elements']:
        if e['id'] not in original:continue
        old=original[e['id']];allowed={'x','y','width','height'}|({'font_size'} if old['type']=='text' else set())
        if {k:v for k,v in e.items() if k not in allowed}!={k:v for k,v in old.items() if k not in allowed}:
            errors.append(e['id']+': protected content/style changed')
        if min(e['width'],e['height'])<=0:errors.append(e['id']+': collapsed box')
        if e['type']=='image' and not math.isclose(e['width']/e['height'],old['width']/old['height'],rel_tol=1e-8):
            errors.append(e['id']+': image box proportion')
    return errors


def metrics(fixture, design, quality=None, render_warnings=()):
    source=fixture['source'];a=analyze(source)
    quality=quality or evaluate(source,design,a)
    result=design_metrics(source,design,a,quality,list(render_warnings))
    result['schema_errors']=schema_errors(design)
    result['preservation_errors']=preserved(source,design)
    result['semantic_collisions']=semantic_collisions(design,fixture['intent'])
    result['bounds_errors']=[e['id'] for e in design['elements'] if not inside(e,design['canvas'])]
    result['ink_bounds_errors']=[e['id'] for e in design['elements'] if e['type']=='text' and
        not inside(ink_box(e,measure_text(e)['ink_bounds']),design['canvas'])]
    out={e['id']:e for e in design['elements']};src={e['id']:e for e in source['elements']}
    result['group_errors']=[s for s in quality['hard_errors'] if 'group' in s or 'label detached' in s]
    result['explicit_groups']={g:[e['id'] for e in design['elements'] if e.get('group_id')==g]
                               for g in sorted({e['group_id'] for e in source['elements'] if e.get('group_id') is not None})}
    containers=[]
    for parent,children in fixture['intent']['containers']:
        for child in children:
            p,c=out[parent],out[child]
            coverage=polygon_overlap(p,c)/(c['width']*c['height'])
            if coverage<.95:containers.append(dict(parent=parent,child=child,coverage=coverage))
    result['lost_containment']=containers
    result['lost_intended_layers']=[list(pair) for pair in fixture['intent']['overlap_pairs']
        if polygon_overlap(src[pair[0]],src[pair[1]])>1 and polygon_overlap(out[pair[0]],out[pair[1]])<1]
    # Exact membership is checked above; geometry errors are also reported by quality.
    centers=[]
    for e in design['elements']:
        if e['id'] in fixture['intent']['backgrounds']+fixture['intent']['decorative']:continue
        old=src[e['id']]
        delta=[(e[p]+e[s]/2)/design['canvas'][s]-(old[p]+old[s]/2)/source['canvas'][s]
               for p,s in [('x','width'),('y','height')]]
        centers.append(math.hypot(*delta))
    result['mean_normalized_center_displacement']=sum(centers)/max(1,len(centers))
    for row in result['images']:
        e=out[row['id']];old=src[row['id']]
        row['box_area_share']=e['width']*e['height']/(design['canvas']['width']*design['canvas']['height'])
        row['relative_area_share']=row['box_area_share']/(old['width']*old['height']/(source['canvas']['width']*source['canvas']['height']))
        if row['existing_asset']:
            # Inspect alpha of renderer-fitted existing art. Never write/replace assets.
            raster=load_asset_image(str(ASSETS),e['asset_id'],e['width'],e['height'],e.get('fit','contain'))
            bbox=raster.getchannel('A').point(lambda v:255 if v>16 else 0).getbbox()
            row['visible_alpha_extent_px']=[bbox[2]-bbox[0],bbox[3]-bbox[1]] if bbox else [0,0]
        else:row['visible_alpha_extent_px']=None
    return result


def render(design,path):
    notes=render_design_to_png(design,ASSETS,path,max_size=max(design['canvas'].values()))
    with Image.open(path) as im:
        im.load();assert im.size==tuple(design['canvas'][k] for k in ('width','height'))
    return notes


def page(title,body):
    return '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>body{font:16px/1.5 system-ui;margin:28px;background:#faf9f5;color:#222}a{color:#254b8e}
section{border-top:2px solid #aaa;margin:35px 0;padding-top:14px}.native{overflow:auto;background:#ddd;max-height:1050px}
img{display:block;max-width:none;max-height:none}pre{white-space:pre-wrap}table{border-collapse:collapse}th,td{padding:7px;border:1px solid #bbb;text-align:left}summary{cursor:pointer}article{margin:20px 0}</style>
<title>'''+html.escape(title)+'</title><h1>'+html.escape(title)+'</h1>'+body


def panel(stem, title, m):
    fonts='; '.join(f"{e['id']}: {e['font_size']:.2f}px ({e['line_count']} lines)" for e in m['fonts'])
    images='; '.join(f"{e['id']}: {e['width']:.1f} × {e['height']:.1f}px, visible alpha {e['visible_alpha_extent_px']}" for e in m['images'])
    return f'''<article><h3>{html.escape(title)}</h3><p>{len(m['preservation_errors'])} preservation failures;
{len(m['overflows'])} text overflows; {len(m['semantic_collisions'])} annotation-aware box collisions;
{len(m['evaluation']['hard_errors'])} engine hard errors. Heuristic score {m['evaluation']['score']:.2f}.</p>
<p>{html.escape(fonts)}</p><p>{html.escape(images)}</p>
<div class="native"><img src="{stem}.png" alt="{html.escape(title)}"></div>
<p><a href="{stem}.json">Design JSON</a> · <a href="{stem}.png">Native PNG</a></p>
<details><summary>Full measurements, warnings and score breakdown</summary><pre>{html.escape(json.dumps(m,indent=2))}</pre></details></article>'''


def sources(destination):
    fixtures=compositions();assert len(fixtures)==12 and len({f['name'] for f in fixtures})==12
    checks=[];sections=[]
    for f in fixtures:
        s=f['source'];assert not schema_errors(s),(f['name'],schema_errors(s))
        assert len({e['id'] for e in s['elements']})==len(s['elements'])
        missing=[e['id'] for e in s['elements'] if e['type']=='image' and not (ASSETS/e['asset_id']).is_file()]
        assert sorted(missing)==sorted(f['intent']['missing_ids'])
        m=metrics(f,s)
        problems={k:m[k] for k in ('overflows','bounds_errors','ink_bounds_errors','semantic_collisions') if m[k]}
        checks.append(dict(name=f['name'],problems=problems,engine_heuristic_errors=m['evaluation']['hard_errors']))
        stem=f['name']+'-source';save(destination/(stem+'.json'),s)
        m['render_warnings']=render(s,destination/(stem+'.png'))
        save(destination/(f['name']+'-source-metrics.json'),m)
        sections.append('<section><h2>'+f['name']+(' — ADVERSARIAL TARGETS' if f['adversarial'] else '')+'</h2><p>'+html.escape(f['description'])+'</p>'+panel(stem,'Source',m)+'</section>')
    save(destination/'fixtures.json',fixtures);save(destination/'source-validation.json',checks)
    (destination/'sources.html').write_text(page('Source review — before engine execution','<p>Native-size images; scroll instead of automatic shrinking. Engine heuristic overlap warnings are distinct from annotated design intent.</p>'+''.join(sections)))
    print(json.dumps(checks,indent=2),flush=True)
    if any(c['problems'] for c in checks):raise ValueError('Repair source fixtures before reviewing/running outputs')


def run(destination):
    fixtures=json.loads((destination/'fixtures.json').read_text())
    reviewed=json.loads((destination/'source-review.json').read_text())
    assert reviewed['fixtures_sha256']==fingerprint(fixtures) and reviewed['approved_for_evaluation']
    assert fingerprint(fixtures)==fingerprint(compositions()),'Fixtures changed since source review'
    records=[]
    for f in fixtures:
        source=f['source'];before=deepcopy(source);analysis=analyze(source)
        for ti,target in enumerate(f['targets']):
            name=f"{f['name']}-t{ti+1}";stem=name+'-output'
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');output=resize(source,target)
            assert source==before
            notes=render(output,destination/(stem+'.png'));save(destination/(stem+'.json'),output)
            m=metrics(f,output,render_warnings=notes)
            candidates=generate_candidates(source,target,analysis);catalog=[];effective=[]
            folder=destination/name;folder.mkdir(exist_ok=True)
            for i,c in enumerate(candidates):
                raw=evaluate(source,c,analysis)
                fixed=repair(source,c,analysis) if raw['hard_errors'] else c
                q=evaluate(source,fixed,analysis)
                raw_min=min((e['font_size'] for e in c['elements'] if e['type']=='text'),default=None)
                fixed_min=min((e['font_size'] for e in fixed['elements'] if e['type']=='text'),default=None)
                catalog.append(dict(index=i,raw=raw,effective=q,repair_applied=bool(raw['hard_errors']),
                                    raw_min_font=raw_min,effective_min_font=fixed_min))
                effective.append(fixed)
                save(folder/f'candidate-{i:03d}.json',fixed)
                if raw['hard_errors']:save(folder/f'candidate-{i:03d}-raw.json',c)
            winner=min(range(len(catalog)),key=lambda i:(len(catalog[i]['effective']['hard_errors']),catalog[i]['effective']['score'],i))
            assert effective[winner]==output,'Candidate audit must reproduce resize exactly'
            save(folder/'scores.json',catalog)
            record=dict(name=name,fixture=f['name'],target=target,adversarial=f['adversarial'],
                        warning_messages=[str(w.message) for w in caught],metrics=m,
                        selected_index=winner,candidate_count=len(catalog))
            records.append(record)
            print(name,'selected',winner,'errors',len(m['evaluation']['hard_errors']),'minfont',m['min_font_size'],flush=True)
    save(destination/'metrics.json',records)
    save(destination/'environment.json',dict(python=platform.python_version(),platform=platform.platform(),
         packages={k:importlib.metadata.version(k) for k in ('Pillow','skia-python','cr-renderer')},
         commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         renderer_origin=json.loads(importlib.metadata.distribution('cr-renderer').read_text('direct_url.json'))))
    report(destination)


def candidates(destination,names):
    """Export selected, original-composition and alternative diagnostic candidates.

    Chosen using fixed diagnostic axes (score, smallest font, source composition,
    image box area). They are not engine improvements or replacement selections.
    """
    fixtures={f['name']:f for f in json.loads((destination/'fixtures.json').read_text())}
    records={r['name']:r for r in json.loads((destination/'metrics.json').read_text())}
    for name in names:
        record=records[name];f=fixtures[record['fixture']];folder=destination/name
        catalog=json.loads((folder/'scores.json').read_text());rank=lambda row:(len(row['effective']['hard_errors']),row['effective']['score'],row['index'])
        choices=[record['selected_index'],0,1]
        choices += [r['index'] for r in sorted(catalog,key=rank)[:3]]
        choices += [min(catalog,key=lambda r:(len(r['effective']['hard_errors']),-(r['effective_min_font'] or 0)))['index']]
        choices += [min(catalog,key=lambda r:(len(r['effective']['hard_errors']),r['effective']['penalties']['composition']))['index']]
        choices += [min(catalog,key=lambda r:(len(r['effective']['hard_errors']),r['effective']['penalties']['image_scale']))['index']]
        choices=list(dict.fromkeys(choices));sections=[]
        for i in choices:
            d=json.loads((folder/f'candidate-{i:03d}.json').read_text())
            notes=render(d,folder/f'candidate-{i:03d}.png');m=metrics(f,d,render_warnings=notes)
            save(folder/f'candidate-{i:03d}-metrics.json',m)
            sections.append('<section>'+panel(f'candidate-{i:03d}',f'Candidate {i}'+(' — SELECTED' if i==record['selected_index'] else ''),m)+
                            '<details><summary>Before/after repair score</summary><pre>'+html.escape(json.dumps(catalog[i],indent=2))+'</pre></details></section>')
            rawpath=folder/f'candidate-{i:03d}-raw.json'
            if rawpath.exists():
                raw=json.loads(rawpath.read_text());rn=render(raw,folder/f'candidate-{i:03d}-raw.png')
                sections.append(panel(f'candidate-{i:03d}-raw',f'Candidate {i} before repair',metrics(f,raw,render_warnings=rn)))
        save(folder/'preview-indices.json',choices)
        (folder/'index.html').write_text(page(name+' — candidate investigation','<p>Local heuristic scores only. Selection sorts by hard-error count, then score, then index. All candidate JSONs and raw/effective scores are retained. <a href="scores.json">All scores</a></p>'+''.join(sections)))
        print(name,'preview candidates',choices,flush=True)
    report(destination)


def report(destination):
    fixtures=json.loads((destination/'fixtures.json').read_text());records=json.loads((destination/'metrics.json').read_text())
    review=json.loads((destination/'review.json').read_text()) if (destination/'review.json').exists() else {}
    body='<p>12 distinct sources × 2 targets. Development probes, not an unseen benchmark or official scoring. Sources were rendered and reviewed first. All previews are native CSS pixel size (scroll horizontally). Existing assets only. <a href="sources.html">Source validation/review</a> · <a href="metrics.json">All metrics</a> · <a href="environment.json">Environment</a></p>'
    if review:
        body+='<h2>Human visual findings</h2><ol>'
        for finding in review.get('ranked_patterns', []):
            body+='<li><strong>'+html.escape(finding['pattern'])+'</strong>: '+html.escape(finding['diagnosis'])+'</li>'
        body+='</ol><p>Alpha extents are fitted-asset proxies before scene rotation, opacity and occlusion. Font thresholds are warnings, not official pass/fail criteria.</p>'
    body+='<h2>Task index</h2><table><tr><th>Task</th><th>Min font px</th><th>Engine errors / overflow</th><th>Visual review</th></tr>'
    for r in records:
        m=r['metrics'];assessment=review.get('per_task',{}).get(r['name'],{}).get('visual_assessment','pending')
        body+=f'<tr><td><a href="#{r["name"]}">{r["name"]}</a></td><td>{m["min_font_size"]:.2f}</td><td>{len(m["evaluation"]["hard_errors"])} / {len(m["overflows"])}</td><td>{html.escape(assessment)}</td></tr>'
    body+='</table>'
    for f in fixtures:
        body+='<section><h2>'+f['name']+(' — ADVERSARIAL' if f['adversarial'] else '')+'</h2><p>'+html.escape(f['description'])+'</p>'
        sm=json.loads((destination/(f['name']+'-source-metrics.json')).read_text())
        body+=panel(f['name']+'-source','Source',sm)
        for r in records:
            if r['fixture']!=f['name']:continue
            observation=review.get('per_task',{}).get(r['name'],{})
            body+=f'<div id="{r["name"]}"><p><strong>Visual review:</strong> {html.escape(observation.get("notes","Pending"))}</p></div>'
            body+=panel(r['name']+'-output',r['name']+f" — {r['target']['width']} × {r['target']['height']}, candidate {r['selected_index']}",r['metrics'])
            if (destination/r['name']/'index.html').exists():body+=f'<p><a href="{r["name"]}/index.html">Candidate preview investigation</a></p>'
        body+='</section>'
    (destination/'index.html').write_text(page('CHAMELEON generalization evaluation',body))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['sources','run','candidates','report']);p.add_argument('--out',type=Path,required=True);p.add_argument('--tasks',nargs='*',default=[]);args=p.parse_args()
    out=args.out.resolve()
    assert out.is_relative_to(ROOT/'artifacts'),'Keep evaluation artifacts under artifacts/'
    out.mkdir(parents=True,exist_ok=True)
    with patch.object(socket.socket,'connect',side_effect=RuntimeError('Network disabled for evaluation')):
        if args.phase=='sources':sources(out)
        elif args.phase=='run':run(out)
        elif args.phase=='candidates':candidates(out,args.tasks)
        else:report(out)


if __name__=='__main__':main()
