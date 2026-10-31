"""Find GHS diamonds on a page by their red outline, then name them by comparing with templates.

Rendering the page means embedded images and vector drawings are handled the same way.
"""
import json
import math
from pathlib import Path

import pymupdf

SIZE = 32  # templates are SIZE x SIZE grey pixels
SCALE = 2  # render at 144 dpi, which keeps the thin diamond outline in one piece
SMALLEST = 18  # points; anything shorter is a bullet or a letter
MAX_FILL = 0.55  # a diamond is an outline, so red can only fill part of its box
TEMPLATE_FILE = Path(__file__).with_name("sign_templates.json")
TEMPLATES = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8")) if TEMPLATE_FILE.exists() else {}


def red_blobs(pix):
    """Return (left, top, right, bottom, pixels) for each group of red pixels, bridging gaps of 2 pixels."""
    width, height, stride, samples = pix.width, pix.height, pix.stride, pix.samples
    seen = bytearray(width * height)
    wanted = bytearray(width * height)
    for y in range(height):
        row = y * stride
        for x in range(width):
            r, g, b = samples[row + x * 3:row + x * 3 + 3]
            wanted[y * width + x] = r > 150 and r - g > 70 and r - b > 70
    blobs = []
    for begin in range(width * height):
        if not wanted[begin] or seen[begin]:
            continue
        seen[begin] = 1
        stack, left, right, top, bottom, count = [begin], width, 0, height, 0, 0
        while stack:
            index = stack.pop()
            y, x = divmod(index, width)
            left, right, top, bottom = min(left, x), max(right, x), min(top, y), max(bottom, y)
            count += 1
            for ny in range(max(0, y - 2), min(height, y + 3)):
                for nx in range(max(0, x - 2), min(width, x + 3)):
                    near = ny * width + nx
                    if wanted[near] and not seen[near]:
                        seen[near] = 1
                        stack.append(near)
        blobs.append((left, top, right + 1, bottom + 1, count))
    return blobs


def sign_rects(page, clip):
    """Return the page rectangles of diamonds inside clip, in reading order, splitting diamonds that touch."""
    clip = clip & page.rect
    if clip.is_empty:
        return []
    pix = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), clip=clip, colorspace=pymupdf.csRGB, alpha=False)
    rects = []
    for left, top, right, bottom, count in red_blobs(pix):
        width, height = (right - left) / SCALE, (bottom - top) / SCALE
        parts = max(1, round(width / height))
        if height < SMALLEST or not 0.8 < width / parts / height < 1.25 or count / (right - left) / (bottom - top) > MAX_FILL:
            continue
        for part in range(parts):
            x = clip.x0 + left / SCALE + part * width / parts
            rects.append(pymupdf.Rect(x, clip.y0 + top / SCALE, x + width / parts, clip.y0 + bottom / SCALE))
    return sorted(rects, key=lambda rect: (round(rect.y0 / 40), rect.x0))


def grey_cells(page, rect):
    """Return rect as SIZE x SIZE grey values, averaged so that thin lines survive at any print size."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
    totals, counts = [0] * SIZE * SIZE, [0] * SIZE * SIZE
    for y in range(pix.height):
        for x in range(pix.width):
            cell = (y * SIZE // pix.height) * SIZE + x * SIZE // pix.width
            totals[cell] += pix.samples[y * pix.stride + x]
            counts[cell] += 1
    return [total // max(count, 1) for total, count in zip(totals, counts)]


def similarity(a, b):
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    top = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    return top / (math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b)) or 1)


def name_signs(page, clip):
    """Return [(template name, similarity)] for the diamonds inside clip."""
    named = []
    for rect in sign_rects(page, clip):
        cells = grey_cells(page, rect)
        named.append(max(((name, similarity(cells, template)) for name, template in TEMPLATES.items()),
                         key=lambda pair: pair[1], default=("", 0.0)))
    return named
