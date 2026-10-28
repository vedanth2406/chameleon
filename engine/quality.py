"""Internal feasibility checks and deterministic heuristic costs (not official)."""
from collections import Counter
from copy import deepcopy
from itertools import combinations
import math

from engine.contracts import Analysis, Evaluation
from engine.geometry import bounds, ink_box, inside, place_uniform, polygon_overlap
from engine.layout import contain_unit
from engine.groups import label_pair, valid_label_pair
from engine.relationships import text_links, text_gap
from engine.typography import fit_text, measure_text
from engine.validation import schema_errors
from engine.spatial_relationships import penalties as relationship_penalties, supported_pairs

MUTABLE = {'x', 'y', 'width', 'height', 'font_size'}


def evaluate(source: dict, candidate: dict, analysis: Analysis) -> Evaluation:
    errors = schema_errors(candidate)
    costs = dict(readability=0., microscopic=0., headline_prominence=0., image_recognition=0., text_cohesion=0.,
                 hierarchy=0., collisions=0., spacing=0., composition=0., image_scale=0.,
                 containment=0., layering=0.)
    if errors:
        return Evaluation(hard_errors=errors, penalties=costs, score=sum(costs.values()))
    src = {e['id']: e for e in source['elements']}
    out = {e['id']: e for e in candidate['elements']}
    if Counter(e['id'] for e in candidate['elements']) != Counter(e['id'] for e in source['elements']):
        errors.append('element ID multiplicities differ')
    canvas = candidate['canvas']
    backgrounds = set(analysis['background_ids'])
    decorations = set(analysis['decoration_ids'])
    importance = {i: u['importance'] for u in analysis['units'] for i in u['element_ids']}
    roles = {i: u['role'] for u in analysis['units'] for i in u['element_ids']}
    unit_of = {i: u['key'] for u in analysis['units'] for i in u['element_ids']}
    for eid, e in out.items():
        old = src.get(eid)
        if old is None:
            continue
        allowed = MUTABLE if old['type'] == 'text' else MUTABLE - {'font_size'}
        if {k: v for k, v in old.items() if k not in allowed} != {k: v for k, v in e.items() if k not in allowed}:
            errors.append(f'{eid}: protected fields changed')
        if e['type'] != old['type']:
            return Evaluation(hard_errors=errors, penalties=costs, score=sum(costs.values()))
        if e['width'] <= 0 or e['height'] <= 0:
            errors.append(f'{eid}: nonpositive box')
        if not inside(e, canvas):
            errors.append(f'{eid}: box or rotated bounds outside canvas')
        if old['type'] == 'image' and eid not in backgrounds:
            if not math.isclose(e['width'] * old['height'], e['height'] * old['width'], rel_tol=1e-6, abs_tol=1e-6):
                errors.append(f'{eid}: foreground image box distorted')
            expected = math.sqrt(old['width'] * old['height'] * canvas['width'] * canvas['height'] /
                                 (source['canvas']['width'] * source['canvas']['height']))
            actual = math.sqrt(max(1e-9, e['width'] * e['height']))
            costs['image_scale'] += 3 * importance[eid] * max(0., math.log(expected / actual)) ** 2
            aspect = old['width'] / old['height']
            desired_short = min(min(old['width'], old['height']),
                                min(64., canvas['height']*.7) if .65 <= aspect <= 1.6
                                else min(32., canvas['height']*.3))
            costs['image_recognition'] += 12 * importance[eid] * max(
                0., desired_short / max(1e-9, min(e['width'], e['height'])) - 1) ** 2
        if e['type'] == 'text':
            measured = measure_text(e)
            if measured['overflow_x'] or measured['overflow_y']:
                errors.append(f'{eid}: text overflow')
            if not inside(ink_box(e, measured['ink_bounds']), canvas):
                errors.append(f'{eid}: rendered text ink outside canvas')
            desired = min(old['font_size'], 12. + 6. * importance[eid])
            costs['readability'] += 20 * importance[eid] * max(0., math.log(desired / e['font_size'])) ** 2
            # Use rendered integer glyph size. Costs below the readability
            # floor grow quadratically in inverse size, not merely log(size).
            floor = min(old['font_size'], 7. if roles[eid] == 'fine_print' else 9.)
            mass = 1 + .75 * min(1., len(e['content']) / 160)
            costs['microscopic'] += 45 * importance[eid] * mass * max(
                0., floor / max(1, int(e['font_size'])) - 1) ** 2
        if eid not in backgrounds | decorations:
            nx = (e['x'] + e['width'] / 2) / canvas['width']
            ny = (e['y'] + e['height'] / 2) / canvas['height']
            ox = (old['x'] + old['width'] / 2) / source['canvas']['width']
            oy = (old['y'] + old['height'] / 2) / source['canvas']['height']
            aspect_change = abs(math.log((canvas['width'] / canvas['height']) /
                                        (source['canvas']['width'] / source['canvas']['height'])))
            costs['composition'] += (40 if aspect_change < .35 else 1.) * importance[eid] * ((nx - ox) ** 2 + (ny - oy) ** 2)
    for unit in analysis['units']:
        if len(unit['element_ids']) < 2 or not all(i in out for i in unit['element_ids']):
            continue
        old_members, new_members = [src[i] for i in unit['element_ids']], [out[i] for i in unit['element_ids']]
        if label_pair(old_members):
            if not valid_label_pair(old_members, new_members):
                errors.append(f"{unit['key']}: label detached from background")
            continue
        ox, oy, ow, oh = bounds(old_members)
        nx, ny, nw, nh = bounds(new_members)
        for old, new in zip(old_members, new_members):
            for k, origin_old, length_old, origin_new, length_new in (
                    ('x', ox, ow, nx, nw), ('y', oy, oh, ny, nh)):
                if length_old and length_new and abs((old[k] - origin_old) / length_old - (new[k] - origin_new) / length_new) > 1e-4:
                    errors.append(f"{unit['key']}: group geometry changed")
                    break
                dimension = 'width' if k == 'x' else 'height'
                if length_old and length_new and abs(old[dimension] / length_old - new[dimension] / length_new) > 1e-4:
                    errors.append(f"{unit['key']}: group proportions changed")
    intentional = {frozenset(p) for p in analysis['intentional_overlap_pairs']}
    intentional.update(supported_pairs(analysis, out))
    foreground = [e for e in candidate['elements'] if e['id'] not in backgrounds | decorations and e['id'] in src]
    for a, b in combinations(foreground, 2):
        if unit_of[a['id']] == unit_of[b['id']] or frozenset((a['id'], b['id'])) in intentional:
            continue
        area = polygon_overlap(a, b)
        fraction = area / max(1e-9, min(a['width'] * a['height'], b['width'] * b['height']))
        costs['collisions'] += 200 * fraction
        if fraction > .015:
            errors.append(f"{a['id']} / {b['id']}: unintended overlap")
    texts = [e for e in foreground if e['type'] == 'text']
    ordinary = [e['font_size'] for e in texts if roles[e['id']] != 'headline']
    for e in texts:
        if roles[e['id']] == 'headline' and ordinary:
            costs['headline_prominence'] += 35 * max(0., 1.35 * max(ordinary) / e['font_size'] - 1) ** 2
    for a, b in combinations(texts, 2):
        original_ratio = src[a['id']]['font_size'] / src[b['id']]['font_size']
        new_ratio = a['font_size'] / b['font_size']
        costs['hierarchy'] += 2 * abs(math.log(new_ratio / original_ratio)) / max(1, len(texts))
        if src[a['id']].get('group_id') is None and src[b['id']].get('group_id') is None:
            old_dx = abs(src[a['id']]['x'] + src[a['id']]['width'] / 2 - src[b['id']]['x'] - src[b['id']]['width'] / 2)
            if old_dx < source['canvas']['width'] * .08:
                dx = abs(a['x'] + a['width'] / 2 - b['x'] - b['width'] / 2)
                costs['spacing'] += 4 * dx / canvas['width']
    unit_boxes = [bounds([out[i] for i in u['element_ids']], rotated=True)
                  for u in analysis['units'] if u['role'] not in ('background', 'decoration')
                  and all(i in out for i in u['element_ids'])]
    desired_gap = min(canvas.values()) * .02
    for a, b in combinations(unit_boxes, 2):
        dx = max(0., a[0] - b[0] - b[2], b[0] - a[0] - a[2])
        dy = max(0., a[1] - b[1] - b[3], b[1] - a[1] - a[3])
        costs['spacing'] += max(0., 1 - math.hypot(dx, dy) / desired_gap)
    change = abs(math.log((canvas['width']/canvas['height']) /
                          (source['canvas']['width']/source['canvas']['height'])))
    if change > .35:
        for aid,bid in text_links(source,analysis):
            if aid not in out or bid not in out:continue
            a,b=out[aid],out[bid]
            overlap=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
            if overlap >= .65*min(a['width'],b['width']) and b['y']>=a['y']:
                gap=b['y']-a['y']-a['height']
                costs['text_cohesion'] += .5*max(0.,gap/text_gap(a,b)-2) ** 2
    costs['containment'], costs['layering'] = relationship_penalties(source, candidate, analysis)
    return Evaluation(hard_errors=list(dict.fromkeys(errors)), penalties=costs, score=sum(costs.values()))


def repair(source: dict, candidate: dict, analysis: Analysis) -> dict:
    """Restore protected fields and missing IDs, contain groups, refit typography.

    Best effort: collision reflow is handled by the candidate search. Re-evaluate.
    """
    out = deepcopy(source)
    out['canvas'] = deepcopy(candidate['canvas'])
    proposed = {e['id']: e for e in candidate.get('elements', [])}
    by_id = {e['id']: e for e in out['elements']}
    for e in out['elements']:
        patch = proposed.get(e['id'], {})
        for key in MUTABLE if e['type'] == 'text' else MUTABLE - {'font_size'}:
            value = patch.get(key, e.get(key))
            if isinstance(value, (int, float)) and math.isfinite(value) and (key in ('x', 'y') or value > 0):
                e[key] = max(1., value) if key == 'font_size' else value
        if e['type'] == 'image' and e['id'] not in analysis['background_ids']:
            original = next(s for s in source['elements'] if s['id'] == e['id'])
            e['height'] = e['width'] * original['height'] / original['width']
    for unit in analysis['units']:
        members = [by_id[i] for i in unit['element_ids']]
        original_members = [e for e in source['elements'] if e['id'] in unit['element_ids']]
        if len(members) > 1 and not valid_label_pair(original_members, members):
            rect = bounds(members, rotated=True)
            restored = [deepcopy(e) for e in source['elements'] if e['id'] in unit['element_ids']]
            if any(e['type'] == 'image' or e.get('rotation', 0) for e in restored):
                place_uniform(restored, rect)
            else:
                ox, oy, ow, oh = bounds(restored)
                x, y, w, h = rect
                for e in restored:
                    e['x'], e['y'] = x + (e['x'] - ox) * w / ow, y + (e['y'] - oy) * h / oh
                    e['width'] *= w / ow
                    e['height'] *= h / oh
            for e in restored:
                if e['type'] == 'text':
                    e['font_size'] = by_id[e['id']]['font_size']
                by_id[e['id']].update(e)
        contain_unit(members, out['canvas'])
        for e in members:
            if e['type'] == 'text':
                e.update(fit_text(e))
    from engine.relationship_layout import restore_layers, wrap_containers
    restore_layers(source, out, analysis)
    wrap_containers(out, analysis)
    return out
