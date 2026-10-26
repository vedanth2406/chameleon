"""Conservative rules for compacting a simple shape-backed label as one unit."""
from engine.geometry import box, intersection


def label_pair(members):
    """Only one rectangle and one contained text box with matching rotation.

    General groups remain rigid. For a label pair, box padding may change but
    the label's normalized center and containment must remain intact.
    """
    if len(members) != 2:
        return None
    shapes = [e for e in members if e['type'] == 'shape' and e.get('shape_type') == 'rectangle']
    texts = [e for e in members if e['type'] == 'text']
    if len(shapes) != 1 or len(texts) != 1:
        return None
    background, label = shapes[0], texts[0]
    if background.get('rotation', 0) != label.get('rotation', 0):
        return None
    if intersection(box(background), box(label)) < label['width'] * label['height'] - 1e-6:
        return None
    if background['width'] <= 0 or background['height'] <= 0:
        return None
    return background, label


def label_center(background, label):
    return ((label['x'] + label['width']/2 - background['x']) / background['width'],
            (label['y'] + label['height']/2 - background['y']) / background['height'])


def valid_label_pair(original, proposed):
    old, new = label_pair(original), label_pair(proposed)
    return (old is not None and new is not None and
            all(abs(a-b) < 1e-4 for a,b in zip(label_center(*old),label_center(*new))))
