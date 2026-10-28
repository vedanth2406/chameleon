"""Optional relationship-aware planning; schema groups are never rewritten."""
from copy import deepcopy

from engine.geometry import bounds, place_uniform
from engine.spatial_relationships import STRONG


def wrap_containers(design, analysis):
    """Fit supported rectangular panels to complete, independently placed units.

    Other content is not absorbed. If the envelope covers an unrelated element,
    normal collision validation rejects the candidate. Padding may shrink at a
    canvas edge; the container is never made transparent or zero-sized.
    """
    by_id = {e['id']: e for e in design['elements']}
    cw, ch = design['canvas']['width'], design['canvas']['height']
    for r in analysis.get('containers', []):
        if r['confidence'] < STRONG:
            continue
        members = [by_id[i] for i in r['child_ids']]
        x, y, w, h = bounds(members, rotated=True)
        left, top, right, bottom = r['padding']
        # One padding scale avoids exaggerating the border after a large reflow.
        padding_scale = min(w, h)
        pad = [max(2., min(.08, v)*padding_scale) for v in (left, top, right, bottom)]
        x0, y0 = max(0., x-pad[0]), max(0., y-pad[1])
        x1, y1 = min(cw, x+w+pad[2]), min(ch, y+h+pad[3])
        if x1 > x0 and y1 > y0:
            by_id[r['container_id']].update(x=x0, y=y0, width=x1-x0, height=y1-y0)


def restore_layers(source, design, analysis):
    """Repair a high-confidence pair as one envelope, never through graph closure."""
    original = {e['id']: e for e in source['elements']}
    by_id = {e['id']: e for e in design['elements']}
    for r in analysis.get('layers', []):
        if r['confidence'] < STRONG:
            continue
        rect = bounds([by_id[i] for i in r['element_ids']], rotated=True)
        members = [deepcopy(original[i]) for i in r['element_ids']]
        place_uniform(members, rect)
        from engine.layout import contain_unit
        contain_unit(members, design['canvas'])
        for e in members:
            by_id[e['id']].update(e)


def relationship_candidates(source, target, analysis, base_generator):
    containers = [r for r in analysis.get('containers', []) if r['confidence'] >= STRONG]
    layers = [r for r in analysis.get('layers', []) if r['confidence'] >= STRONG]
    if not containers and not layers:
        return []
    planning = deepcopy(analysis)
    parent_ids = {r['container_id'] for r in containers}
    # Container geometry is derived AFTER its child units have been laid out.
    # All child units retain independence, so rows/columns/partitions can reflow.
    planning['units'] = [u for u in planning['units'] if not parent_ids.intersection(u['element_ids'])]
    original = {e['id']: e for e in source['elements']}
    for r in layers:
        ids = set(r['element_ids'])
        units = [u for u in planning['units'] if ids.intersection(u['element_ids'])]
        if len(units) != 2 or any(len(u['element_ids']) != 1 for u in units):
            continue
        planning['units'] = [u for u in planning['units'] if u not in units]
        planning['units'].append(dict(key='layer:'+units[0]['key']+'|'+units[1]['key'],
                                     element_ids=list(r['element_ids']),
                                     source_bounds=bounds([original[i] for i in r['element_ids']], rotated=True),
                                     role='image', importance=max(u['importance'] for u in units)))
    planning['units'].sort(key=lambda u: (u['source_bounds'][1], u['source_bounds'][0], u['key']))
    results = base_generator(source, target, planning)
    for design in results:
        wrap_containers(design, analysis)
    # A second planning family reserves a contiguous slot for each enclosure.
    # Its children then reflow inside that slot. This avoids enveloping an
    # unrelated group interleaved by a flat shelf/partition arrangement.
    if containers:
        from engine.layout import _stack
        enclosed = deepcopy(planning)
        packed = []
        for relation in containers:
            ids = set(relation['child_ids'])
            children = [u for u in enclosed['units'] if ids.intersection(u['element_ids'])]
            if not children or any(not set(u['element_ids']) <= ids for u in children):
                continue
            enclosed['units'] = [u for u in enclosed['units'] if u not in children]
            enclosed['units'].append(dict(key='enclosure:'+relation['container_id'],
                element_ids=relation['child_ids'][:], role='group',
                source_bounds=bounds([original[i] for i in relation['child_ids']]),
                importance=max(u['importance'] for u in children)))
            packed.append((relation, children))
        enclosed['units'].sort(key=lambda u: (u['source_bounds'][1], u['source_bounds'][0], u['key']))
        for design in base_generator(source, target, enclosed):
            for axis in ('x', 'y'):
                variant = deepcopy(design)
                by_id = {e['id']: e for e in variant['elements']}
                for relation, children in packed:
                    rectangle = bounds([by_id[i] for i in relation['child_ids']], rotated=True)
                    # Restore source geometry before placing each independent
                    # child unit; keep layer assemblies intact if present.
                    for i in relation['child_ids']:
                        by_id[i].update(deepcopy(original[i]))
                    gap = min(rectangle[2:]) * .035
                    _stack(children, by_id, original, rectangle, 1., gap, axis)
                wrap_containers(variant, analysis)
                results.append(variant)
    return results
