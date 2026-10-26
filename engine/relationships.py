"""Conservative source-space links between adjacent standalone text units."""
from engine.geometry import box


def text_links(source, analysis):
    by_id = {e['id']: e for e in source['elements']}
    texts = [by_id[u['element_ids'][0]] for u in analysis['units']
             if len(u['element_ids']) == 1 and by_id[u['element_ids'][0]]['type'] == 'text'
             and not by_id[u['element_ids'][0]].get('rotation', 0)]
    texts.sort(key=lambda e: (e['y'], e['x'], e['id']))
    links = []
    for a, b in zip(texts, texts[1:]):
        ax, ay, aw, ah = box(a); bx, by, bw, bh = box(b)
        overlap = max(0., min(ax+aw, bx+bw)-max(ax, bx))
        gap = by-ay-ah
        if (overlap >= .65*min(aw,bw) and -.15*min(ah,bh) <= gap <=
                max(1.5*max(a['font_size'],b['font_size']),.025*source['canvas']['height'])):
            links.append((a['id'],b['id']))
    return links


def text_gap(a, b):
    return max(3., .35*min(a['font_size'],b['font_size']) + .1*max(a['font_size'],b['font_size']))
