"""Regular polygon geometry and non-overwriting output helpers.

Coordinates describe pixel *boundaries*: a W by H canvas spans [0, W] x [0, H].
The same vertices drive standalone masks and tessellation previews.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw


SHAPES = ('circle', 'rectangle', 'triangle', 'hexagon', 'ellipse',
          'rounded_rectangle', 'pentagon', 'octagon', 'star')


def polygon_geometry(shape, width, height):
    """Return vertices, bounding box, and side length for a centered polygon."""
    if width <= 0 or height <= 0:
        raise ValueError('Canvas dimensions must be positive')
    cx, cy = width / 2, height / 2
    if shape == 'triangle':
        side = min(width, height * 2 / math.sqrt(3))
        altitude = side * math.sqrt(3) / 2
        vertices = [(cx, cy - altitude / 2),
                    (cx + side / 2, cy + altitude / 2),
                    (cx - side / 2, cy + altitude / 2)]
    elif shape == 'hexagon':
        side = min(width / 2, height / math.sqrt(3))
        half_height = math.sqrt(3) * side / 2
        vertices = [(cx + side, cy), (cx + side / 2, cy + half_height),
                    (cx - side / 2, cy + half_height), (cx - side, cy),
                    (cx - side / 2, cy - half_height),
                    (cx + side / 2, cy - half_height)]
    elif shape in ('pentagon', 'octagon'):
        count = 5 if shape == 'pentagon' else 8
        radius = min(width, height) / 2
        vertices = [(cx + radius * math.cos(-math.pi / 2 + 2 * math.pi * i / count),
                     cy + radius * math.sin(-math.pi / 2 + 2 * math.pi * i / count))
                    for i in range(count)]
        side = 2 * radius * math.sin(math.pi / count)
    else:
        raise ValueError('Polygon geometry requires a supported polygon')
    xs, ys = zip(*vertices)
    return {'vertices': vertices, 'bounds': (min(xs), min(ys), max(xs), max(ys)),
            'side': side}


def polygon_mask(shape, width, height):
    """Four-times supersampled mask with coverage antialiasing, no outer halo."""
    vertices = polygon_geometry(shape, width, height)['vertices']
    scale = 2 if width * height > 4_000_000 else 4
    mask = Image.new('L', (width * scale, height * scale), 0)
    ImageDraw.Draw(mask).polygon([(round(x * scale), round(y * scale))
                                  for x, y in vertices], fill=255)
    # BOX averages coverage without the ringing produced by a Lanczos mask.
    return mask.resize((width, height), Image.Resampling.BOX)


def shape_mask(shape, width, height, *, corner_radius=.18, star_points=5, star_inner_ratio=.5):
    if not math.isfinite(corner_radius) or not 0 <= corner_radius <= .5:
        raise ValueError('Corner radius ratio must be between 0 and 0.5')
    if type(star_points) is not int or not 3 <= star_points <= 16:
        raise ValueError('Star point count must be between 3 and 16')
    if not math.isfinite(star_inner_ratio) or not .1 <= star_inner_ratio <= .9:
        raise ValueError('Star inner radius ratio must be between 0.1 and 0.9')
    if shape in ('triangle', 'hexagon', 'pentagon', 'octagon'):
        return polygon_mask(shape, width, height)
    scale = 2 if width * height > 4_000_000 else 4
    mask = Image.new('L', (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(mask)
    if shape == 'ellipse':
        draw.ellipse((0, 0, width * scale - 1, height * scale - 1), fill=255)
    elif shape == 'rounded_rectangle':
        radius = round(min(width, height) * corner_radius * scale)
        draw.rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=radius, fill=255)
    elif shape == 'star':
        cx, cy = width * scale / 2, height * scale / 2
        outer = min(width, height) * scale / 2
        vertices = []
        for i in range(star_points * 2):
            angle = -math.pi / 2 + i * math.pi / star_points
            radius = outer if i % 2 == 0 else outer * star_inner_ratio
            vertices.append((round(cx + radius * math.cos(angle)),
                             round(cy + radius * math.sin(angle))))
        draw.polygon(vertices, fill=255)
    else:
        raise ValueError(f'Unknown shape {shape!r}')
    return mask.resize((width, height), Image.Resampling.BOX)


def unused_path(path):
    """Select a numbered alternative when an output already exists."""
    path = Path(path)
    candidate = path
    number = 1
    while candidate.exists():
        candidate = path.with_name(f'{path.stem}_{number:03d}{path.suffix}')
        number += 1
    return candidate


def save_png(image, path):
    """Save a PNG without replacing an existing file; return the actual path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        destination = unused_path(path)
        try:
            handle = destination.open('xb')
        except FileExistsError:
            continue
        with handle:
            image.save(handle, 'PNG', optimize=True)
        return destination
