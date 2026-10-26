"""Local Skia metrics using the supplied converter's font lookup and wrapping.

Measurement follows the converter (including inclusive run ends) without changing
source content/runs. Full font ascent/descent gives conservative vertical bounds.
"""
from copy import deepcopy
from functools import lru_cache
import math
from pathlib import Path
from typing import Optional

import skia
from cr_renderer.fonts import normalize_family
from renderer.converter.brand_fonts import load_brand_font_manager
from renderer.converter.wrap import char_widths, wrap_text


@lru_cache(maxsize=1)
def font_manager():
    return load_brand_font_manager(str(Path(__file__).resolve().parents[1] / 'brand_kit' / 'fonts'))


@lru_cache(maxsize=8192)
def _metrics(family, bold, italic, size, text):
    weight = 'bold' if bold else 'regular'
    style = 'bolditalic' if bold and italic else 'bold' if bold else 'italic' if italic else 'regular'
    manager = font_manager()
    widths = tuple(char_widths(manager, family, weight, style, size, text))
    face = skia.Typeface.MakeFromData(manager.lookup(family, weight, style))
    font = skia.Font(face, size)
    fm = font.getMetrics()
    glyph_bounds = tuple((r.left(), r.top() - fm.fAscent, r.right(), r.bottom() - fm.fAscent)
                         for r in font.getBounds(font.textToGlyphs(text)))
    return widths, fm.fDescent - fm.fAscent, glyph_bounds


def measure_text(element: dict) -> dict:
    """Return width/height in px, line_count, overflow flags, and method.

    Wrap using base-font metrics exactly as the supplied converter does; then
    measure rendered spans at integer font size, with style overrides/spacing.
    No content is clipped, even when max_lines or the box height is exceeded.
    """
    text = element['content']
    size = float(element['font_size'])
    if not math.isfinite(size) or size < 1:
        raise ValueError('font_size must be finite and at least 1')
    family = element['font_family']
    bold = element.get('font_weight', 'regular') == 'bold'
    italic = element.get('font_style', 'normal') == 'italic'
    base, _, _ = _metrics(family, bold, italic, size, text)
    wrapped = wrap_text(text, list(base), float(element['width']))
    styles = [(bold, italic, element.get('color'))] * len(text)
    for run in element.get('style_runs', []):
        for i in range(max(0, run['start']), min(len(text), run['end'] + 1)):
            b, it, color = styles[i]
            styles[i] = (run.get('font_weight', 'bold' if b else 'regular') == 'bold',
                         run.get('font_style', 'italic' if it else 'normal') == 'italic',
                         run.get('color', color))
    lines = wrapped.split('\n') if text else []
    offset, max_width, max_height = 0, 0., 0.
    ink_points = []
    spacing = float(element.get('letter_spacing', 0))
    for line_index, line in enumerate(lines):
        width, line_height, j = 0., 0., 0
        line_ink = []
        while j < len(line):
            end = j + 1
            while end < len(line) and styles[offset + end] == styles[offset + j]:
                end += 1
            b, it, _ = styles[offset + j]
            span = line[j:end]
            if element.get('capitalize', False):
                span = span.upper()
            widths, height, glyph_bounds = _metrics(family, b, it, float(int(size)), span)
            advance = width
            for k, (advance_width, rect) in enumerate(zip(widths, glyph_bounds)):
                left, top, right, bottom = rect
                if right > left and bottom > top:
                    line_ink.extend(((advance + k * spacing + left, top),
                                     (advance + k * spacing + right, bottom)))
                advance += advance_width
            width += sum(widths) + spacing * max(0, len(span) - 1)
            line_height = max(line_height, height)
            j = end
        if not line:
            _, line_height, _ = _metrics(family, bold, italic, float(int(size)), '')
        alignment = element.get('text_align', 'left')
        dx = (element['width'] - width) * (.5 if alignment == 'center' else 1. if alignment == 'right' else 0.)
        dy = line_index * size * (element.get('line_height', 1.2) or 1.)
        ink_points.extend((x + dx, y + dy) for x, y in line_ink)
        if line_ink:
            width = max(width, max(x for x, _ in line_ink) - min(x for x, _ in line_ink))
        max_width, max_height = max(max_width, width), max(max_height, line_height)
        offset += len(line) + 1
    height = max_height + max(0, len(lines) - 1) * size * (element.get('line_height', 1.2) or 1.) if lines else 0.
    max_lines = element.get('max_lines')
    ink = (0., 0., 0., 0.)
    if ink_points:
        xs, ys = zip(*ink_points)
        ink = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        height = max(height, max(ys))
    fallback = normalize_family(family) not in font_manager()._fonts
    return dict(width=max_width, height=height, line_count=len(lines),
                overflow_x=max_width > element['width'] + 1e-6,
                overflow_y=height > element['height'] + 1e-6 or (max_lines is not None and len(lines) > max_lines),
                ink_bounds=ink,
                measurement_method='skia-local-fonts/converter-wrap/conservative-font-height' +
                ('/family-fallback' if fallback else ''))


def fit_text(element: dict, max_font_size: Optional[float] = None) -> dict:
    """Copy the element and change only font_size; unresolved overflow stays visible."""
    out = deepcopy(element)
    cap = float(element['font_size'] if max_font_size is None else max_font_size)
    if not math.isfinite(cap) or cap < 1:
        raise ValueError('max_font_size must be finite and at least 1')
    def fits(size):
        out['font_size'] = size
        m = measure_text(out)
        return not (m['overflow_x'] or m['overflow_y'])
    if fits(cap):
        return out
    if (element.get('letter_spacing', 0) or element.get('capitalize', False) or
            any('font_weight' in r or 'font_style' in r for r in element.get('style_runs', []))):
        # The converter wraps without spacing or per-run font overrides.
        # Consequently fitting is NOT monotonic: a smaller font can put more
        # spaced characters on one line and overflow where a larger one fits.
        # Search quarter-pixel sizes, bounded by the single-line font height.
        _, minimum_height, _ = _metrics(element['font_family'], False, False, 1., '')
        upper = min(cap, element['height'] / max(minimum_height, 1e-9) + 1)
        for step in range(int(upper * 4), 3, -1):
            if fits(step / 4):
                return out
        out['font_size'] = 1.
        return out
    # Renderer uses integer glyph sizes. Search integers for stable wrapping;
    # always remeasure the final choice rather than trusting an estimate.
    best, lo, hi = 1., 1, int(cap)
    while lo <= hi:
        middle = (lo + hi) // 2
        if fits(float(middle)):
            best, lo = float(middle), middle + 1
        else:
            hi = middle - 1
    out['font_size'] = best
    return out
