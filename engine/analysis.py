"""Deterministic geometry-based hints; IDs and copy carry no semantic labels."""
import math
from itertools import combinations
from pathlib import Path

from engine.contracts import Analysis
from engine.geometry import bounds, box, intersection, polygon_overlap

ASSETS = Path(__file__).resolve().parents[1] / 'brand_kit' / 'assets'


def analyze(source: dict) -> Analysis:
    elements = sorted(source['elements'], key=lambda e: (
        e['y'], e['x'], e.get('z_index', 0), e['type'], e['id']))
    cw, ch = source['canvas']['width'], source['canvas']['height']
    backgrounds, decorations, diagnostics = [], [], []
    min_z = min((e.get('z_index', 0) for e in elements), default=0)
    for e in elements:
        coverage = intersection(box(e), (0, 0, cw, ch)) / (cw * ch)
        if (e['type'] != 'text' and e.get('group_id') is None
                and coverage >= .9 and e.get('z_index', 0) == min_z):
            backgrounds.append(e['id'])
        elif (e['type'] == 'shape' and e.get('group_id') is None
              and e.get('opacity', 1) <= .35):
            decorations.append(e['id'])
        if e['width'] <= 0 or e['height'] <= 0:
            diagnostics.append(f"{e['id']}: degenerate source box")
        if e['type'] == 'image' and not (ASSETS / e['asset_id']).is_file():
            diagnostics.append(f"{e['id']}: missing asset; preserve renderer placeholder")

    groups, free = {}, []
    for e in elements:
        if e.get('group_id') is not None:
            groups.setdefault(('group', e['group_id']), []).append(e)
        else:
            free.append(e)
    # Infer only tight containment relationships, never mere proximity.
    used = set()
    for shape in free:
        if shape['type'] != 'shape' or shape['id'] in backgrounds + decorations:
            continue
        labels = [e for e in free if e['type'] == 'text' and e['id'] not in used
                  and e.get('z_index', 0) >= shape.get('z_index', 0)
                  and intersection(box(shape), box(e)) >= .95 * e['width'] * e['height']
                  and e['width'] * e['height'] < shape['width'] * shape['height']]
        if len(labels) == 1:
            # A panel containing independent artwork/groups is not just a
            # button for its one free text label. Leave it available for the
            # source-derived enclosure pass after explicit units are built.
            other_content = [e for e in elements if e['id'] not in (shape['id'], labels[0]['id'])
                             and e['id'] not in backgrounds + decorations
                             and (e['type'] == 'image' or e.get('group_id') is not None)
                             and e.get('z_index', 0) >= shape.get('z_index', 0)
                             and intersection(box(shape), box(e)) >= .985 * e['width'] * e['height']]
            if other_content:
                continue
            groups[('inferred', shape['id'])] = [shape, labels[0]]
            used.update(e['id'] for e in groups[('inferred', shape['id'])])
    for e in free:
        if e['id'] not in used:
            groups[('element', e['id'])] = [e]
    max_font = max((e['font_size'] for e in elements if e['type'] == 'text'), default=1)
    units = []
    for (kind, key), members in groups.items():
        texts = [e for e in members if e['type'] == 'text']
        images = [e for e in members if e['type'] == 'image']
        ids = [e['id'] for e in members]
        importance, role = .4, 'shape'
        if all(i in backgrounds for i in ids):
            importance, role = .1, 'background'
        elif all(i in decorations for i in ids):
            importance, role = .15, 'decoration'
        elif len(members) > 1:
            importance, role = .65, 'group'
        elif texts:
            ratio = texts[0]['font_size'] / max_font
            importance = .35 + .65 * ratio
            role = 'headline' if ratio >= .8 else 'text'
            if ratio <= .45 and texts[0]['y'] >= .8 * ch:
                role = 'fine_print'
        elif images:
            importance = .65 + .25 * min(1., math.sqrt(images[0]['width'] * images[0]['height'] / (cw * ch)))
            role = 'image'
        units.append(dict(key=f'{kind}:{key}', element_ids=ids,
                          source_bounds=bounds(members), role=role, importance=importance))
    units.sort(key=lambda u: (u['source_bounds'][1], u['source_bounds'][0], u['key']))
    unit_of = {i: u['key'] for u in units for i in u['element_ids']}
    pairs = []
    for a, b in combinations(elements, 2):
        if polygon_overlap(a, b) <= 1e-8:
            continue
        if (unit_of[a['id']] == unit_of[b['id']] or
                a['id'] in backgrounds + decorations or b['id'] in backgrounds + decorations):
            pairs.append(tuple(sorted((a['id'], b['id']))))
    result = Analysis(units=units, background_ids=sorted(backgrounds),
                      decoration_ids=sorted(decorations),
                      intentional_overlap_pairs=sorted(set(pairs)), diagnostics=diagnostics,
                      containers=[], layers=[])
    from engine.spatial_relationships import infer
    result['containers'], result['layers'] = infer(source, result)
    return result
