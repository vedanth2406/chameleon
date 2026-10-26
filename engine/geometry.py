"""Pixel geometry shared by layout and validation; no rendering side effects."""
import math


def box(element):
    return tuple(float(element[k]) for k in ('x', 'y', 'width', 'height'))


def corners(element):
    x, y, w, h = box(element)
    angle = math.radians(element.get('rotation', 0))
    c, s = math.cos(angle), math.sin(angle)
    return [(x + w / 2 + dx * c - dy * s, y + h / 2 + dx * s + dy * c)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2),
                          (w / 2, h / 2), (-w / 2, h / 2))]


def bounds(elements, rotated=False):
    points = []
    for el in elements:
        x, y, w, h = box(el)
        points.extend(((x, y), (x + w, y + h)))
        if rotated:
            points.extend(corners(el))
    if not points:
        return (0., 0., 0., 0.)
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def intersection(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return max(0., min(ax + aw, bx + bw) - max(ax, bx)) * max(
        0., min(ay + ah, by + bh) - max(ay, by))


def polygon_overlap(a, b):
    """Intersection area of two rotated rectangles, via convex clipping."""
    polygon = corners(a)
    clip = corners(b)
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    for p, q in zip(clip, clip[1:] + clip[:1]):
        previous, polygon = polygon, []
        if not previous:
            break
        for start, end in zip(previous, previous[1:] + previous[:1]):
            ds, de = cross(p, q, start), cross(p, q, end)
            if (ds >= 0) != (de >= 0):
                t = ds / (ds - de)
                polygon.append((start[0] + t * (end[0] - start[0]),
                                start[1] + t * (end[1] - start[1])))
            if de >= 0:
                polygon.append(end)
    return abs(sum(p[0] * q[1] - q[0] * p[1]
                   for p, q in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def inside(element, canvas, tolerance=1e-5):
    x, y, w, h = bounds([element], rotated=True)
    return (x >= -tolerance and y >= -tolerance and
            x + w <= canvas['width'] + tolerance and
            y + h <= canvas['height'] + tolerance)


def ink_box(element, ink_bounds):
    """Transform local text ink to a rectangle rotating about the text box center."""
    ix, iy, iw, ih = ink_bounds
    dx, dy = ix + iw / 2 - element['width'] / 2, iy + ih / 2 - element['height'] / 2
    angle = math.radians(element.get('rotation', 0))
    cx = element['x'] + element['width'] / 2 + dx * math.cos(angle) - dy * math.sin(angle)
    cy = element['y'] + element['height'] / 2 + dx * math.sin(angle) + dy * math.cos(angle)
    return dict(x=cx - iw / 2, y=cy - ih / 2, width=iw, height=ih,
                rotation=element.get('rotation', 0))


def place_uniform(elements, rectangle, enlarge=True):
    """Move/scale a whole unit into a cell, accounting for rotated extents."""
    x, y, w, h = bounds(elements, rotated=True)
    tx, ty, tw, th = rectangle
    scale = min(tw / max(w, 1e-9), th / max(h, 1e-9))
    if not enlarge:
        scale = min(scale, 1.)
    ox, oy = tx + (tw - w * scale) / 2, ty + (th - h * scale) / 2
    for el in elements:
        el['x'] = ox + (el['x'] - x) * scale
        el['y'] = oy + (el['y'] - y) * scale
        el['width'] *= scale
        el['height'] *= scale
        if el['type'] == 'text':
            el['font_size'] = max(1., el['font_size'] * scale)
