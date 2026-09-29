"""Bounded-memory vectorization of the existing Studio texture equations."""
import math
import numpy as np
from PIL import Image, ImageFilter

from marble_circles import MarbleGenerator
from .noise_vector import noise


class FastMarbleGenerator(MarbleGenerator):
    """Same rendering pipeline; evaluate noise in row blocks rather than pixels.

    Only for Studio's deterministic sampling. Legacy CLI rendering stays intact.
    """

    def _generate_texture(self, style, style_name):
        """Assemble color rows without retaining full-size float and index arrays."""
        planetary = style_name in self.PLANETARY_STYLES
        image = Image.new('RGB', (self.width, self.height))
        palette = np.asarray(style.colors)
        for start, _, rows, columns in self._blocks():
            base = (self._horizontal_base_block(style, style_name, rows, columns)
                    if planetary else self._base_pattern_block(style, rows, columns))
            veins = (self._planetary_block(style, style_name, rows, columns)
                     if planetary else self._vein_block(style, rows, columns))
            indices = ((base + 1) / 2 * (len(style.colors) - 1)).astype(int)
            indices = np.clip(indices, 0, len(style.colors) - 1)
            colors = palette[indices]
            levels = (veins * style.vein_intensity + 1) / 2
            factors = 1.0 + (levels - 0.5) * 0.3
            pixels = np.clip(colors * factors[..., None], 0, 255).astype(np.uint8)
            image.paste(Image.fromarray(pixels), (0, start))
        return image.filter(ImageFilter.GaussianBlur(radius=0.5)).convert('RGBA')

    def _blocks(self):
        columns = np.arange(self.width, dtype=np.float64)[None, :]
        # Bound intermediate allocations to about 128K samples at any resolution.
        rows_per_block = max(1, min(128, 131072 // self.width))
        for start in range(0, self.height, rows_per_block):
            end = min(self.height, start + rows_per_block)
            yield start, end, np.arange(start, end, dtype=np.float64)[:, None], columns

    def _latitude(self, rows, strength):
        # Keep Python's scalar pow rounding identical to the reference renderer.
        return np.array([(1 - (abs(int(i) - self.height // 2) /
                             (self.height // 2 - 10)) ** .4) * strength
                         for i in rows[:, 0]])[:, None]

    def _base_block(self, style, rows, columns):
        result = np.zeros(np.broadcast_shapes(rows.shape, columns.shape))
        for octave in range(style.complexity):
            frequency = style.vein_scale * (2 ** octave) * style.texture_scale
            amplitude = 1 / (2 ** octave)
            ox, oy = self.noise_offsets[octave % len(self.noise_offsets)]
            result += amplitude * noise((rows + ox) * frequency, (columns + oy) * frequency, base=42)
        return result

    def _generate_base_noise(self, style):
        result = np.empty((self.height, self.width))
        for start, end, rows, columns in self._blocks():
            result[start:end] = self._base_pattern_block(style, rows, columns)
        return result

    def _base_pattern_block(self, style, rows, columns):
        pattern = getattr(self, 'studio_pattern', 'traditional')
        if pattern == 'ribbon_bands':
            offset = (self.studio_seed % 997) * .137
            drift = noise(rows * .006 * style.texture_scale + offset,
                          columns * .004 * style.texture_scale + offset,
                          octaves=2, base=4100) * 90
            return np.sin((rows + drift) * style.vein_scale * 3) * .78 + \
                noise(rows * .01, columns * .01, base=4101) * .22
        if pattern == 'concentric_rings':
            offset = (self.studio_seed % 997) * .137
            radius = np.hypot((rows - self.height / 2) / max(self.height, 1),
                              (columns - self.width / 2) / max(self.width, 1))
            warp = noise(rows * .008 + offset, columns * .008 + offset, base=4200) * .025
            return np.sin((radius + warp) * self.width * style.vein_scale * 3)
        if pattern == 'cellular_stone':
            frequency = style.vein_scale * style.texture_scale * .8
            x, y = columns * frequency, rows * frequency
            nearest = np.full(np.broadcast_shapes(x.shape, y.shape), np.inf)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    cell_x, cell_y = np.floor(x) + dx, np.floor(y) + dy
                    jitter_x = np.sin(cell_x * 127.1 + cell_y * 311.7 + self.studio_seed) * 43758.5453
                    jitter_y = np.sin(cell_x * 269.5 + cell_y * 183.3 + self.studio_seed) * 22578.1459
                    distance = (x - cell_x - (jitter_x - np.floor(jitter_x))) ** 2 + \
                               (y - cell_y - (jitter_y - np.floor(jitter_y))) ** 2
                    np.minimum(nearest, distance, out=nearest)
            return np.clip(1 - np.sqrt(nearest) * 2, -1, 1)
        return self._base_block(style, rows, columns)

    def _generate_horizontal_base_noise(self, style, planet_type):
        result = np.empty((self.height, self.width))
        for start, end, rows, columns in self._blocks():
            result[start:end] = self._horizontal_base_block(style, planet_type, rows, columns)
        return result

    def _horizontal_base_block(self, style, planet_type, rows, columns):
        strength = {'jupiter': 3., 'earth': 2., 'mars': 1.8, 'alien': 2.5,
                    'volcanic': 2.2, 'ice_world': 1.5, 'ocean_world': 2., 'desert': 1.8}[planet_type]
        scale = style.texture_scale
        rotation = self._latitude(rows, strength)
        primary = noise(rows * .003 * scale, columns * .001 * scale, octaves=2, base=5000) * 180 * rotation
        secondary = noise(rows * .008 * scale, columns * .002 * scale, base=5100) * 100 * rotation
        flowing = columns + (primary + secondary)
        return self._base_block(style, rows, flowing)

    def _generate_vein_pattern(self, style):
        result = np.empty((self.height, self.width))
        for start, end, rows, columns in self._blocks():
            result[start:end] = self._vein_block(style, rows, columns)
        return result

    def _vein_block(self, style, rows, columns):
        scale = style.texture_scale
        x = rows + noise(rows * .008 * scale, columns * .008 * scale, base=100) * 50
        y = columns + noise(rows * .012 * scale, columns * .006 * scale, base=200) * 30
        return noise(x * style.vein_scale * 2 * scale, y * style.vein_scale * 2 * scale,
                     octaves=2, persistence=.7, base=300)

    def _generate_planetary_pattern(self, style, planet_type):
        result = np.empty((self.height, self.width))
        for start, end, rows, columns in self._blocks():
            result[start:end] = self._planetary_block(style, planet_type, rows, columns)
        return result

    def _planetary_block(self, style, planet_type, rows, columns):
        # strength, (frequency x/y, octaves, base) for terrain and detail, detail weight
        options = {
            'earth': (2., (.006, .006, 3, 400), (.015, .012, 2, 500), .3),
            'ocean_world': (2., (.006, .006, 3, 400), (.015, .012, 2, 500), .3),
            'mars': (1.8, (.010, .010, 3, 800), (.020, .008, 2, 900), .4),
            'desert': (1.8, (.010, .010, 3, 800), (.020, .008, 2, 900), .4),
            'ice_world': (1.5, (.012, .012, 2, 1000), (.025, .015, 1, 1100), .3),
            'volcanic': (2.2, (.008, .015, 3, 1200), (.030, .030, 1, 1300), .6),
            'alien': (2.5, (.014, .014, 4, 1400), (.022, .009, 2, 1500), .4),
        }
        scale = style.texture_scale
        strength = 3. if planet_type == 'jupiter' else options[planet_type][0]
        rotation = self._latitude(rows, strength)
        primary = noise(rows * .003 * scale, columns * .001 * scale, octaves=2, base=2000) * 150 * rotation
        secondary = noise(rows * .008 * scale, columns * .002 * scale, base=2100) * 80 * rotation
        flowing = columns + (primary + secondary)
        if planet_type == 'jupiter':
            bands = np.array([math.sin((int(i) - self.height // 2) * .025 * scale) * .8
                              for i in rows[:, 0]])[:, None]
            return bands + noise(rows * .008 * scale, flowing * .025 * scale,
                                 octaves=4, base=600) * .4
        _, terrain, detail, weight = options[planet_type]
        def sample(parameters):
            x, y, octaves, base = parameters
            return noise(rows * x * scale, flowing * y * scale, octaves=octaves, base=base)
        return sample(terrain) + sample(detail) * weight
