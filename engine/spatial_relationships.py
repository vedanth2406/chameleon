"""Conservative source-derived containment and image-layer hints.

No semantic labels, fixture annotations, copy, or asset-name rules. Explicit
layout units remain intact. Confidence is evidence strength, not a probability.
Only strong relationships affect collision exemptions or planning assemblies.
"""
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from PIL import Image
from renderer.converter.colorutil import parse_rgba
from engine.geometry import bounds, ink_box, polygon_overlap

STRONG = .8
ASSETS = Path(__file__).resolve().parents[1] / 'brand_kit' / 'assets'


def overlap_fraction(a, b):
    return polygon_overlap(a, b) / max(1e-9, min(a['width'] * a['height'], b['width'] * b['height']))


@lru_cache(maxsize=256)
def _asset_extent(asset_id):
    """Read existing alpha geometry; absent assets are not positive evidence."""
    try:
        with Image.open(ASSETS / asset_id) as im:
            rgba = im.convert('RGBA')
            extent = rgba.getchannel('A').point(lambda v: 255 if v > 16 else 0).getbbox()
            return rgba.size, extent
    except (OSError, ValueError):
        return None


def content_bounds(element):
    extent = _asset_extent(element['asset_id'])
    if extent is None or extent[1] is None:
        return None
    (iw, ih), (left, top, right, bottom) = extent
    w, h = element['width'], element['height']
    fit = element.get('fit', 'contain')
    if fit == 'fill':
        return left/iw, top/ih, (right-left)/iw, (bottom-top)/ih
    scale = (max if fit == 'cover' else min)(w/iw, h/ih)
    dx, dy = (w-iw*scale)/2, (h-ih*scale)/2
    x0, y0 = max(0., dx+left*scale), max(0., dy+top*scale)
    x1, y1 = min(w, dx+right*scale), min(h, dy+bottom*scale)
    return x0/w, y0/h, max(0., x1-x0)/w, max(0., y1-y0)/h


def visible_box(element, normalized):
    x, y, w, h = normalized
    return ink_box(element, (x*element['width'], y*element['height'],
                             w*element['width'], h*element['height']))


def infer(source, analysis):
    original = {e['id']: e for e in source['elements']}
    excluded = set(analysis['background_ids'] + analysis['decoration_ids'])
    units = [u for u in analysis['units'] if u['role'] not in ('background', 'decoration')]
    area = source['canvas']['width'] * source['canvas']['height']
    containers = []
    for unit in units:
        if len(unit['element_ids']) != 1:
            continue
        parent = original[unit['element_ids'][0]]
        if (parent['type'] != 'shape' or parent.get('shape_type') != 'rectangle'
                or parent.get('group_id') is not None or abs(parent.get('rotation', 0)) > 1e-6):
            continue
        rgba = parse_rgba(parent.get('fill_color'), default=(0, 0, 0, 0.))
        alpha = parent.get('opacity', 1) * rgba[3]
        coverage = parent['width'] * parent['height'] / area
        if not .08 <= coverage <= .85 or alpha < .45:
            continue
        if max(parent['width']/parent['height'], parent['height']/parent['width']) > 8:
            continue  # stripes/connectors are not panels
        children = []
        for child in units:
            if child is unit:
                continue
            members = [original[i] for i in child['element_ids']]
            if not all(e.get('z_index', 0) >= parent.get('z_index', 0) for e in members):
                continue
            if not any(e.get('z_index', 0) > parent.get('z_index', 0) for e in members):
                continue
            if all(polygon_overlap(parent, e) >= .985 * e['width'] * e['height'] for e in members):
                children.append(child)
        if len(children) < 2:
            continue
        child_ids = [i for c in children for i in c['element_ids']]
        x, y, w, h = bounds([original[i] for i in child_ids], rotated=True)
        gaps = (x-parent['x'], y-parent['y'], parent['x']+parent['width']-x-w,
                parent['y']+parent['height']-y-h)
        if min(gaps) < -1e-5:
            continue
        occupancy = sum(c['source_bounds'][2]*c['source_bounds'][3] for c in children) / (parent['width']*parent['height'])
        if not .12 <= occupancy <= .95:
            continue
        padded = min(gaps) >= .012*min(parent['width'], parent['height'])
        # Balanced borders and independently stacked contents distinguish a mat
        # from an incidental large rectangle crossing a composition.
        balanced = max(gaps)/max(1., min(gaps)) <= 4.5
        signals = ['filled rectangle', 'multiple complete units', 'behind contents', 'bounded coverage']
        confidence = .55
        if padded: confidence += .15; signals.append('interior padding')
        if balanced: confidence += .15; signals.append('balanced border')
        containers.append(dict(container_id=parent['id'], child_unit_keys=[c['key'] for c in children],
                               child_ids=child_ids, confidence=confidence, signals=signals,
                               padding=(gaps[0]/w, gaps[1]/h, gaps[2]/w, gaps[3]/h)))
    # One inferred parent per unit, no recursive closure or ancestor absorption.
    occupied = set()
    containers.sort(key=lambda r: (original[r['container_id']]['width']*original[r['container_id']]['height'],
                                   original[r['container_id']]['y'], original[r['container_id']]['x']))
    for relation in containers:
        ids = {relation['container_id'], *relation['child_ids']}
        if relation['confidence'] >= STRONG:
            if ids & occupied:
                relation['confidence'] = .55
                relation['signals'].append('competing enclosure; soft only')
            else:
                occupied.update(ids)

    layers = []
    # Respect arbitrary explicit groups. Only independent image-only singleton
    # units are eligible; never peel an image out of a multi-element group.
    images = [original[u['element_ids'][0]] for u in units
              if len(u['element_ids']) == 1 and original[u['element_ids'][0]]['type'] == 'image']
    for a, b in combinations(images, 2):
        fraction = overlap_fraction(a, b)
        ratio = (a['width']*a['height'])/(b['width']*b['height'])
        aspects = (a['width']/a['height'])/(b['width']/b['height'])
        if not (.08 <= fraction <= .8 and .35 <= ratio <= 2.85 and .5 <= aspects <= 2.):
            continue
        dx = abs(a['x']+a['width']/2-b['x']-b['width']/2)/min(a['width'], b['width'])
        dy = abs(a['y']+a['height']/2-b['y']-b['height']/2)/min(a['height'], b['height'])
        if not (.08 <= dx <= .9 and .06 <= dy <= .9):
            continue
        aa, ba = a.get('rotation', 0), b.get('rotation', 0)
        tilted = min(abs(aa), abs(ba)) >= 3 and abs(aa-ba) >= 10
        translucent = .35 <= min(a.get('opacity', 1), b.get('opacity', 1)) < .9
        stacked = a.get('z_index', 0) != b.get('z_index', 0)
        if not tilted and not translucent:
            continue  # box overlap plus stacking alone is not intent
        ab, bb = content_bounds(a), content_bounds(b)
        visible = overlap_fraction(visible_box(a, ab), visible_box(b, bb)) if ab and bb else 0.
        # Source overlap with unrelated text is negative evidence for an assembly.
        text_conflict = any(e['type'] == 'text' and e['id'] not in excluded and
                            (overlap_fraction(e, a) > .05 or overlap_fraction(e, b) > .05)
                            for e in source['elements'])
        confidence = .5
        signals = ['partial offset overlap', 'comparable image geometry']
        if tilted: confidence += .15; signals.append('contrasting rotations')
        if translucent or stacked: confidence += .1; signals.append('transparency or explicit stacking')
        if .025 <= visible <= .65: confidence += .1; signals.append('visible alpha envelopes overlap')
        if text_conflict: confidence = min(confidence, .5); signals.append('unrelated text intersection; soft only')
        # Require both a deliberate orientation cue and compositing evidence.
        if not (tilted and (translucent or stacked) and .025 <= visible <= .65):
            confidence = min(confidence, .65)
        layers.append(dict(element_ids=(a['id'], b['id']), confidence=confidence, signals=signals,
                           overlap_fraction=fraction, visible_overlap_fraction=visible,
                           content_bounds={a['id']: ab, b['id']: bb} if ab and bb else {}))
    used = set()
    layers.sort(key=lambda r: (-r['confidence'],
                              bounds([original[i] for i in r['element_ids']])[:2]))
    for relation in layers:
        if relation['confidence'] >= STRONG:
            if used.intersection(relation['element_ids']):
                relation['confidence'] = .6
                relation['signals'].append('competing layer edge; soft only')
            else:
                used.update(relation['element_ids'])
    return containers, layers


def supported_pairs(analysis, by_id):
    pairs = set()
    for r in analysis.get('containers', []):
        if r['confidence'] >= STRONG:
            pairs.update(frozenset((r['container_id'], child)) for child in r['child_ids'])
    for r in analysis.get('layers', []):
        a, b = r['element_ids']
        if r['confidence'] >= STRONG and a in by_id and b in by_id:
            # Do not excuse a new near-total occlusion of formerly offset art.
            if overlap_fraction(by_id[a], by_id[b]) <= min(.95, r['overlap_fraction']+.15):
                pairs.add(frozenset((a, b)))
    return pairs


def penalties(source, candidate, analysis):
    original = {e['id']: e for e in source['elements']}
    out = {e['id']: e for e in candidate['elements']}
    containment, layering = 0., 0.
    for r in analysis.get('containers', []):
        if r['container_id'] not in out or any(i not in out for i in r['child_ids']):
            continue
        parent = out[r['container_id']]
        loss = sum((1-min(1., polygon_overlap(parent, out[i])/max(1e-9, out[i]['width']*out[i]['height'])))**2
                   for i in r['child_ids']) / len(r['child_ids'])
        containment += (120 if r['confidence'] >= STRONG else 4) * r['confidence'] * loss
    for r in analysis.get('layers', []):
        if any(i not in out for i in r['element_ids']):
            continue
        a, b = (out[i] for i in r['element_ids'])
        actual = overlap_fraction(a, b)
        loss = max(0., 1-actual/max(1e-9, r['overlap_fraction']))**2
        loss += max(0., actual-r['overlap_fraction'])**2
        if r['content_bounds'] and r['visible_overlap_fraction'] > 0:
            visible = overlap_fraction(visible_box(a, r['content_bounds'][a['id']]),
                                       visible_box(b, r['content_bounds'][b['id']]))
            loss += max(0., 1-visible/r['visible_overlap_fraction'])**2
        old_members = [original[i] for i in r['element_ids']]
        ox, oy, ow, oh = bounds(old_members, rotated=True)
        nx, ny, nw, nh = bounds([a, b], rotated=True)
        geometry = sum(((new[k]-n)/max(1e-9, ns)-(old[k]-o)/max(1e-9, os))**2
                       for old, new in zip(old_members, (a, b))
                       for k, o, os, n, ns in [('x', ox, ow, nx, nw), ('y', oy, oh, ny, nh),
                                             ('width', 0, ow, 0, nw), ('height', 0, oh, 0, nh)])
        layering += (60 if r['confidence'] >= STRONG else 2) * r['confidence'] * (loss+geometry)
    return containment, layering
