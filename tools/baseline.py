"""Original stretch baseline retained only for development comparisons."""
from copy import deepcopy


def stretch(source, target):
    out = deepcopy(source)
    out['canvas'] = deepcopy(target)
    sx = target['width'] / source['canvas']['width']
    sy = target['height'] / source['canvas']['height']
    for e in out['elements']:
        for key in ('x', 'width'):
            e[key] *= sx
        for key in ('y', 'height'):
            e[key] *= sy
        if e['type'] == 'text':
            e['font_size'] = max(1., e['font_size'] * min(sx, sy))
    return out
