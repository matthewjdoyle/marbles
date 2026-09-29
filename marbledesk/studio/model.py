"""Validated, serializable application state. No Qt dependency."""
from dataclasses import asdict, dataclass, field, replace
import json
import math
from pathlib import Path
import random
import colorsys

from marble_circles import MarbleGenerator, MarbleStyle
from marble_shapes import SHAPES
from .branding import APP_NAME

SCHEMA_VERSION = 3
RENDERER_VERSION = 'deterministic-1'
PLANET_TYPES = {key: MarbleGenerator.MARBLE_STYLES[key].name
                for key in MarbleGenerator.PLANETARY_STYLES}
PATTERNS = {'traditional': 'Traditional marble', 'planetary': 'Planetary',
            'ribbon_bands': 'Ribbon bands', 'concentric_rings': 'Concentric rings',
            'cellular_stone': 'Cellular stone'}
PALETTES = {key: (style.name, tuple('#%02X%02X%02X' % c for c in style.colors))
            for key, style in MarbleGenerator.MARBLE_STYLES.items()}
PALETTES.update({
    'teal_copper': ('Teal and copper', ('#073B3A', '#147D78', '#B87333', '#E3B778')),
    'amethyst': ('Amethyst', ('#241138', '#663399', '#A57BC1', '#E4CFF1')),
    'terracotta': ('Terracotta', ('#753B30', '#B55E45', '#DA9270', '#F1CFB1')),
    'midnight_blue': ('Midnight blue', ('#091326', '#172B50', '#365584', '#93A9C8')),
})
RANGES = {
    'intensity': (0.1, 2.0), 'vein_intensity': (0.3, 1.2),
    'vein_scale': (0.010, 0.030), 'complexity': (2, 5),
    'texture_scale': (0.5, 2.0),
}
SCHEMES = ('random', 'analogous', 'complementary', 'triadic', 'monochromatic')


def number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a number')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}')
    if integer and not isinstance(value, int):
        raise ValueError(f'{label} must be an integer')


@dataclass(frozen=True)
class Design:
    colors: tuple = ('#F8F8FF', '#F0F0F0', '#E8E8E8', '#D3D3D3')
    shape: str = 'circle'
    width: int = 1024
    height: int = 1024
    intensity: float = 1.0
    vein_intensity: float = 0.4
    vein_scale: float = 0.015
    complexity: int = 3
    texture_scale: float = 1.0
    seed: int = 42
    renderer_version: str = RENDERER_VERSION
    pattern: str = 'traditional'
    planet_type: str = 'earth'
    palette: str = 'carrara'
    corner_radius: float = .18
    star_points: int = 5
    star_inner_ratio: float = .5

    def __post_init__(self):
        if self.renderer_version != RENDERER_VERSION:
            raise ValueError('This design uses an unsupported renderer version')
        if (self.shape not in SHAPES or self.pattern not in PATTERNS or
                self.planet_type not in PLANET_TYPES or self.palette not in PALETTES):
            raise ValueError('Unknown pattern family or shape')
        number(self.width, 64, 8192, 'Width', True)
        number(self.height, 64, 8192, 'Height', True)
        if self.shape == 'circle' and self.width != self.height:
            raise ValueError('Circles require equal width and height')
        if not isinstance(self.colors, (tuple, list)) or len(self.colors) < 2:
            raise ValueError('A palette needs at least two colors')
        if any(not isinstance(c, str) for c in self.colors):
            raise ValueError('Palette colors must be hexadecimal strings')
        MarbleStyle('Validation', self.colors)
        object.__setattr__(self, 'colors', tuple('#' + c.lstrip('#').upper() for c in self.colors))
        for name, bounds in RANGES.items():
            number(getattr(self, name), *bounds, name.replace('_', ' ').title(), name == 'complexity')
        number(self.seed, 0, 2**31 - 1, 'Seed', True)
        number(self.corner_radius, 0, .5, 'Corner radius')
        number(self.star_points, 3, 16, 'Star points', True)
        number(self.star_inner_ratio, .1, .9, 'Star inner radius ratio')

    @classmethod
    def preset(cls, name, **options):
        style = MarbleGenerator.MARBLE_STYLES[name]
        return cls(pattern='planetary' if name in PLANET_TYPES else 'traditional',
                   planet_type=name if name in PLANET_TYPES else 'earth',
                   palette=name, colors=PALETTES[name][1],
                   vein_intensity=style.vein_intensity, vein_scale=style.vein_scale,
                   complexity=style.complexity, texture_scale=style.texture_scale, **options)

    @classmethod
    def from_dict(cls, value):
        try:
            value = dict(value)
            old_style = value.pop('style', None)
            if 'pattern' not in value:
                value['pattern'] = 'planetary' if old_style in PLANET_TYPES else 'traditional'
                if old_style in PLANET_TYPES:
                    value['planet_type'] = old_style
            if value['pattern'] in PLANET_TYPES:
                value['planet_type'] = value['pattern']
                value['pattern'] = 'planetary'
            if 'palette' not in value:
                value['palette'] = old_style or 'carrara'
            return cls(**value)
        except (TypeError, KeyError, AttributeError) as error:
            raise ValueError('Invalid design document') from error


@dataclass(frozen=True)
class BatchSettings:
    count: int = 8
    palette: bool = False
    texture: bool = False
    scheme: str = 'analogous'
    sizes: tuple = ()  # Empty means current canvas; entries are (width, height).
    ranges: dict = field(default_factory=lambda: dict(RANGES))

    def __post_init__(self):
        number(self.count, 1, 1000, 'Batch count', True)
        if type(self.palette) is not bool or type(self.texture) is not bool or self.scheme not in SCHEMES:
            raise ValueError('Invalid batch variation settings')
        try:
            sizes = tuple(tuple(s) for s in self.sizes)
            for size in sizes:
                if len(size) != 2:
                    raise ValueError('Each batch size needs a width and height')
                for n in size:
                    number(n, 64, 8192, 'Batch dimension', True)
            if set(self.ranges) != set(RANGES):
                raise ValueError('Batch ranges must contain all texture parameters')
            for key, bounds in self.ranges.items():
                if len(bounds) != 2 or bounds[0] > bounds[1]:
                    raise ValueError(f'Invalid range for {key}')
                for v in bounds:
                    number(v, *RANGES[key], key, key == 'complexity')
        except (TypeError, KeyError) as error:
            raise ValueError('Invalid batch sizes or ranges') from error
        object.__setattr__(self, 'sizes', sizes)
        object.__setattr__(self, 'ranges', {k: tuple(v) for k, v in self.ranges.items()})


@dataclass(frozen=True)
class Composition:
    tiles: tuple = ()
    width: int = 1920
    height: int = 1080
    tile_size: int = 240

    def __post_init__(self):
        number(self.width, 64, 8192, 'Wallpaper width', True)
        number(self.height, 64, 8192, 'Wallpaper height', True)
        number(self.tile_size, 64, 2048, 'Tile canvas size', True)
        object.__setattr__(self, 'tiles', tuple(self.tiles))
        if any(not isinstance(t, Design) for t in self.tiles):
            raise ValueError('Tiles must be design recipes')
        shapes = {t.shape for t in self.tiles}
        if len(shapes) > 1 or shapes - {'triangle', 'hexagon'}:
            raise ValueError('Use triangles or hexagons of one shape per composition')

    @classmethod
    def from_dict(cls, value):
        try:
            return cls(**{**value, 'tiles': tuple(Design.from_dict(t) for t in value.get('tiles', []))})
        except (TypeError, AttributeError) as error:
            raise ValueError('Invalid tile composition') from error


@dataclass(frozen=True)
class Document:
    design: Design = field(default_factory=Design)
    batch: BatchSettings = field(default_factory=BatchSettings)
    composition: Composition = field(default_factory=Composition)
    seed_locked: bool = False
    schema_version: int = SCHEMA_VERSION

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('schema_version') not in (1, 2, SCHEMA_VERSION):
            raise ValueError(f'Unsupported {APP_NAME} document version')
        if type(data.get('seed_locked', False)) is not bool:
            raise ValueError('Seed lock must be true or false')
        try:
            return cls(Design.from_dict(data['design']), BatchSettings(**data.get('batch', {})),
                       Composition.from_dict(data.get('composition', {})), data.get('seed_locked', False))
        except (KeyError, TypeError) as error:
            raise ValueError(f'Invalid {APP_NAME} document') from error

    @classmethod
    def load(cls, path):
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError('The selected file is not a valid JSON document') from error


def random_palette(rng, count, scheme):
    """Existing color schemes, sampled from a private RNG."""
    hue, saturation = rng.random(), rng.uniform(0.4, 0.9)
    colors = []
    for i in range(count):
        if scheme == 'random':
            h, s, v = rng.random(), rng.uniform(.4, .9), rng.uniform(.3, .9)
        elif scheme == 'analogous':
            h, s, v = hue + i * .08, max(.2, min(.9, saturation + rng.uniform(-.2, .2))), rng.uniform(.4, .9)
        elif scheme == 'complementary':
            h = hue + (0 if i < count // 2 else .5) + rng.uniform(-.05, .05)
            s, v = max(.2, min(.9, saturation + rng.uniform(-.2, .2))), rng.uniform(.3, .9)
        elif scheme == 'triadic':
            h = hue + (0, .33, .67)[i % 3] + rng.uniform(-.03, .03)
            s, v = max(.3, min(.9, saturation + rng.uniform(-.15, .15))), rng.uniform(.4, .9)
        else:
            h, s, v = hue + rng.uniform(-.02, .02), rng.uniform(.3, .9), rng.uniform(.3, .9)
        colors.append('#%02X%02X%02X' % tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1, s, v)))
    return tuple(colors)


def batch_recipes(design, settings):
    rng = random.Random(design.seed)
    recipes = []
    for width, height in settings.sizes or ((design.width, design.height),):
        for _ in range(settings.count):
            changes = dict(width=width, height=height, seed=rng.randrange(2**31))
            if settings.palette:
                changes['colors'] = random_palette(rng, len(design.colors), settings.scheme)
            if settings.texture:
                for key, (low, high) in settings.ranges.items():
                    changes[key] = rng.randint(low, high) if key == 'complexity' else rng.uniform(low, high)
            recipes.append(replace(design, **changes))
    return recipes
