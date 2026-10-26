"""Independent design candidates, preserving source styles and unit membership."""
from copy import deepcopy
import math

from engine.contracts import Analysis
from engine.geometry import bounds, place_uniform
from engine.typography import fit_text, measure_text


def _prepare(source, target, analysis):
    design = deepcopy(source)
    design['canvas'] = deepcopy(target)
    by_id = {e['id']: e for e in design['elements']}
    sx, sy = target['width'] / source['canvas']['width'], target['height'] / source['canvas']['height']
    for unit in analysis['units']:
        members = [by_id[i] for i in unit['element_ids']]
        if unit['role'] == 'background':
            for e in members:
                e.update(x=0., y=0., width=float(target['width']), height=float(target['height']))
                if e.get('rotation', 0):
                    place_uniform([e], (0, 0, target['width'], target['height']))
        elif unit['role'] == 'decoration':
            for e in members:
                e['x'] *= sx
                e['y'] *= sy
                e['width'] *= min(sx, sy)
                e['height'] *= min(sx, sy)
            contain_unit(members, target)
    return design, by_id


def contain_unit(members, canvas):
    x, y, w, h = bounds(members, rotated=True)
    if w > canvas['width'] or h > canvas['height']:
        place_uniform(members, (0, 0, canvas['width'], canvas['height']), enlarge=False)
    x, y, w, h = bounds(members, rotated=True)
    dx = max(0., -x) - max(0., x + w - canvas['width'])
    dy = max(0., -y) - max(0., y + h - canvas['height'])
    for e in members:
        e['x'] += dx
        e['y'] += dy


def _fit_members(members):
    for e in members:
        if e['type'] == 'text':
            e.update(fit_text(e))


def _composition_candidates(source: dict, target_canvas: dict, analysis: Analysis) -> list[dict]:
    """A composition-preserving candidate and a conservative uniform fallback."""
    candidates = []
    cw, ch = target_canvas['width'], target_canvas['height']
    sx, sy = cw / source['canvas']['width'], ch / source['canvas']['height']
    foreground = [u for u in analysis['units'] if u['role'] not in ('background', 'decoration')]
    for preserve_centers in (True, False):
        design, by_id = _prepare(source, target_canvas, analysis)
        if preserve_centers:
            for u in foreground:
                members = [by_id[i] for i in u['element_ids']]
                x, y, w, h = bounds(members, rotated=True)
                scale = min(sx, sy)
                rect = ((x + w / 2) * sx - w * scale / 2,
                        (y + h / 2) * sy - h * scale / 2, w * scale, h * scale)
                place_uniform(members, rect)
                contain_unit(members, target_canvas)
                _fit_members(members)
        else:
            members = [by_id[i] for u in foreground for i in u['element_ids']]
            if members:
                margin = min(cw, ch) * .025
                place_uniform(members, (margin, margin, cw - 2 * margin, ch - 2 * margin))
                _fit_members(members)
        candidates.append(design)
    return candidates


def _demand(unit, source_by_id, width, font_scale):
    members = [source_by_id[i] for i in unit['element_ids']]
    if len(members) == 1 and members[0]['type'] == 'text':
        e = deepcopy(members[0])
        e.update(width=width, height=1e9, font_size=max(1., e['font_size'] * font_scale))
        return max(1., measure_text(e)['height'])
    _, _, w, h = bounds(members, rotated=True)
    return width * h / max(w, 1e-9)


def _place(unit, by_id, rectangle, font_scale):
    members = [by_id[i] for i in unit['element_ids']]
    x, y, w, h = rectangle
    if len(members) == 1 and members[0]['type'] == 'text':
        e = members[0]
        cap = max(1., e['font_size'] * font_scale)
        e.update(x=x, y=y, width=w, height=h)
        if e.get('rotation', 0):
            place_uniform([e], rectangle)
        e.update(fit_text(e, cap))
        # The renderer top-aligns text. Compact its box to center the actual
        # block in the slot, preserving text_align and all original styles.
        if not e.get('rotation', 0):
            measured = measure_text(e)
            compact_height = min(h, measured['height'] + .1)
            e['y'] += (h - compact_height) / 2
            e['height'] = compact_height
    else:
        caps = {e['id']: max(1., e.get('font_size', 1) * font_scale) for e in members}
        if len(members) > 1 and all(e['type'] != 'image' and not e.get('rotation', 0) for e in members):
            ox, oy, ow, oh = bounds(members)
            compact_w = min(w, ow * font_scale * 1.25)
            needed_h = oh * compact_w / ow
            for e in members:
                if e['type'] == 'text':
                    probe = dict(e, width=e['width'] * compact_w / ow,
                                 height=1e9, font_size=caps[e['id']])
                    needed_h = max(needed_h, measure_text(probe)['height'] * oh / e['height'])
            compact_h = min(h, needed_h)
            x, y = x + (w - compact_w) / 2, y + (h - compact_h) / 2
            w, h = compact_w, compact_h
            sx, sy = w / ow, h / oh
            # Shared affine transform keeps labels in their original relative
            # positions while allowing a button to adapt its shape to its slot.
            for e in members:
                e['x'], e['y'] = x + (e['x'] - ox) * sx, y + (e['y'] - oy) * sy
                e['width'] *= sx
                e['height'] *= sy
        else:
            place_uniform(members, rectangle)
        for e in members:
            if e['type'] == 'text':
                e.update(fit_text(e, caps[e['id']]))


def _stack(units, by_id, source_by_id, rectangle, font_scale, gap, axis='y', exponent=1.):
    if not units:
        return
    x, y, w, h = rectangle
    if axis == 'y':
        weights = [_demand(u, source_by_id, w, font_scale) ** exponent for u in units]
        extent = h
    else:
        weights = []
        for u in units:
            members = [source_by_id[i] for i in u['element_ids']]
            _, _, uw, uh = bounds(members, rotated=True)
            weights.append((uw / max(uh, 1e-9)) ** exponent)
        extent = w
    gap = min(gap, extent / max(1, len(units)) * .15)
    available = extent - gap * (len(units) - 1)
    cursor = y if axis == 'y' else x
    for u, weight in zip(units, weights):
        size = available * weight / sum(weights)
        rect = (x, cursor, w, size) if axis == 'y' else (cursor, y, size, h)
        _place(u, by_id, rect, font_scale)
        cursor += size + gap


def _partition(units, weights, rectangle, gap, bias=1.):
    """Balanced binary space partition; retains order, gives each unit a cell."""
    if not units:
        return []
    if len(units) == 1:
        return [(units[0], rectangle)]
    x, y, w, h = rectangle
    total = sum(weights)
    cut = min(range(1, len(units)), key=lambda k: abs(sum(weights[:k]) - total / 2))
    fraction = sum(weights[:cut]) / total
    if w > h * bias:
        g = min(gap, w * .04)
        a = (w - g) * fraction
        rects = ((x, y, a, h), (x + a + g, y, w - a - g, h))
    else:
        g = min(gap, h * .04)
        a = (h - g) * fraction
        rects = ((x, y, w, a), (x, y + a + g, w, h - a - g))
    return (_partition(units[:cut], weights[:cut], rects[0], gap, bias) +
            _partition(units[cut:], weights[cut:], rects[1], gap, bias))



def generate_candidates(source: dict, target_canvas: dict, analysis: Analysis) -> list[dict]:
    """Search composition, shelves, recursive partitions and editorial bands.

    Stable enumeration order breaks score ties. No content/ID/target catalog
    branching; all decisions depend on geometry, inferred units and font metrics.
    """
    candidates = _composition_candidates(source, target_canvas, analysis)
    units = [u for u in analysis['units'] if u['role'] not in ('background', 'decoration')]
    if not units:
        return candidates
    original = {e['id']: e for e in source['elements']}
    cw, ch = target_canvas['width'], target_canvas['height']
    font_scale = min(1.5, max(.8, math.sqrt(cw * ch / (source['canvas']['width'] * source['canvas']['height']))))
    margin, gap = min(cw, ch) * .035, min(cw, ch) * .025
    rect = (margin, margin, cw - 2 * margin, ch - 2 * margin)
    for axis in ('x', 'y'):
        for exponent in (.5, 1.):
            design, by_id = _prepare(source, target_canvas, analysis)
            _stack(units, by_id, original, rect, font_scale, gap, axis, exponent)
            candidates.append(design)
    role_order = {'image': 0, 'headline': 1, 'text': 2, 'group': 3, 'shape': 4}
    orders = [units, sorted(units, key=lambda u: (role_order.get(u['role'], 5), u['source_bounds'][1], u['source_bounds'][0], u['key']))]
    for ordered in orders:
        weights = []
        for u in ordered:
            members = [original[i] for i in u['element_ids']]
            text_cost = sum(max(1, len(e['content'])) * e['font_size'] ** 2 * .65
                            for e in members if e['type'] == 'text')
            _, _, uw, uh = bounds(members, rotated=True)
            weights.append(max(text_cost, uw * uh * .35, 1.) ** .65)
        for bias in (.65, 1., 1.8):
            design, by_id = _prepare(source, target_canvas, analysis)
            for u, cell in _partition(ordered, weights, rect, gap, bias):
                _place(u, by_id, cell, font_scale)
            candidates.append(design)
    images = [u for u in units if u['role'] == 'image']
    texts = [u for u in units if len(u['element_ids']) == 1 and original[u['element_ids'][0]]['type'] == 'text']
    accessories = [u for u in units if u not in images and u not in texts]
    # Editorial bands give short labels a shared row instead of wasting a
    # column per badge. Several allocations trade image area against text area.
    if images and texts:
        for image_share in (.10, .18, .27):
            for accessory_share in (.22, .32):
                for text_exponent in (0., .5, .75, 1.):
                    design, by_id = _prepare(source, target_canvas, analysis)
                    x, y, w, h = rect
                    if cw / ch >= 1.35:
                        iw = w * image_share
                        _stack(images, by_id, original, (x, y, iw, h), font_scale, gap, 'y', .65)
                        tx, tw = x + iw + gap, w - iw - gap
                        ah = h * accessory_share if accessories else 0
                        _stack(texts, by_id, original, (tx, y, tw, h - ah - (gap if ah else 0)), font_scale, gap, exponent=text_exponent)
                        _stack(accessories, by_id, original, (tx, y + h - ah, tw, ah), font_scale, gap, 'x', .6)
                    else:
                        ih = h * image_share
                        _stack(images, by_id, original, (x, y, w, ih), font_scale, gap, 'x', .65)
                        ah = h * accessory_share if accessories else 0
                        _stack(texts, by_id, original, (x, y + ih + gap, w, h - ih - ah - gap * (2 if ah else 1)), font_scale, gap, exponent=text_exponent)
                        _stack(accessories, by_id, original, (x, y + h - ah, w, ah), font_scale, gap, 'x', .6)
                    candidates.append(design)
        # Side-by-side image / copy / action columns, useful for wide banners.
        if cw / ch >= 1.5 and accessories:
            for image_share, accessory_share in ((.24, .24), (.18, .28), (.32, .2)):
                design, by_id = _prepare(source, target_canvas, analysis)
                x, y, w, h = rect
                iw, aw = w * image_share, w * accessory_share
                _stack(images, by_id, original, (x, y, iw, h), font_scale, gap, exponent=.7)
                _stack(texts, by_id, original, (x + iw + gap, y, w - iw - aw - 2 * gap, h), font_scale, gap)
                _stack(accessories, by_id, original, (x + w - aw, y, aw, h), font_scale, gap, exponent=.6)
                candidates.append(design)
    footers = [u for u in texts if u['role'] == 'fine_print']
    main_texts = [u for u in texts if u not in footers]
    if footers and main_texts and images and cw / ch >= 1.35:
        for image_share in (.10, .18):
            for footer_share in (.14, .20):
                for action_share in (.25, .35):
                    for text_exponent in (0., .5, .8):
                        design, by_id = _prepare(source, target_canvas, analysis)
                        x, y, w, h = rect
                        fh = h * footer_share
                        _stack(footers, by_id, original, (x, y + h - fh, w, fh), font_scale, gap)
                        mh = h - fh - gap
                        iw = w * image_share
                        _stack(images, by_id, original, (x, y, iw, mh), font_scale, gap, exponent=.65)
                        tx, tw = x + iw + gap, w - iw - gap
                        ah = mh * action_share if accessories else 0
                        _stack(main_texts, by_id, original, (tx, y, tw, mh - ah - (gap if ah else 0)), font_scale, gap, exponent=text_exponent)
                        _stack(accessories, by_id, original, (tx, y + mh - ah, tw, ah), font_scale, gap, 'x', .6)
                        candidates.append(design)
    from engine.horizontal import horizontal_candidates, coherent_text_candidates
    candidates.extend(horizontal_candidates(source, target_canvas, analysis, _prepare))
    candidates.extend(coherent_text_candidates(source, target_canvas, analysis, candidates))
    return candidates
