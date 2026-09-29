"""Compare the accelerated path with the independent, existing C sampler."""
from contextlib import redirect_stdout
import io
import unittest

import numpy as np
from noise import pnoise2
from marble_circles import MarbleGenerator, MarbleStyle
from marbledesk.studio.fast_renderer import FastMarbleGenerator
from marbledesk.studio.noise_vector import noise


class AccelerationTests(unittest.TestCase):
    def test_noise_matches_c_sampler_at_boundaries_and_random_coordinates(self):
        rng = np.random.default_rng(728)
        x = np.r_[rng.uniform(-2500, 2500, 1000), [-1024, -1, -.0001, 0, 1, 255, 256, 1024]]
        y = np.r_[rng.uniform(-2500, 2500, 1000), [1024, -1, -.0001, 0, 1, 255, 256, -1024]]
        for octaves, persistence, base in [(1, .5, 42), (2, .7, 300), (3, .5, 400),
                                           (4, .5, 600), (2, .5, 5000)]:
            expected = [pnoise2(float(a + base * .137), float(b + base * .173),
                               octaves=octaves, persistence=persistence, base=0) for a, b in zip(x, y)]
            np.testing.assert_array_equal(noise(x, y, octaves=octaves, persistence=persistence, base=base), expected)

    def test_every_style_and_shape_preserves_final_pixels(self):
        with redirect_stdout(io.StringIO()):
            for style in MarbleGenerator.MARBLE_STYLES:
                for shape in ('circle', 'rectangle', 'triangle', 'hexagon'):
                    with self.subTest(style=style, shape=shape):
                        width, height = (80, 80) if shape == 'circle' else (80, 97)
                        options = dict(shape=shape, style_name=style, deterministic_noise=True, intensity=1.7)
                        old = MarbleGenerator(width=width, height=height, seed=379).generate_marble(**options)
                        new = FastMarbleGenerator(width=width, height=height, seed=379).generate_marble(**options)
                        self.assertEqual(old.tobytes(), new.tobytes())

    def test_multiple_row_blocks_and_custom_parameters(self):
        with redirect_stdout(io.StringIO()):
            for style in ('carrara', 'jupiter', 'alien'):
                custom = MarbleStyle('Test', ['#000000', '#FFFACA', '#298AEE'], 1.1, .027, 5, 1.93)
                options = dict(shape='rectangle', style_name=style, deterministic_noise=True, custom_style=custom)
                old = MarbleGenerator(width=300, height=259, seed=491).generate_marble(**options)
                new = FastMarbleGenerator(width=300, height=259, seed=491).generate_marble(**options)
                self.assertEqual(old.tobytes(), new.tobytes())


if __name__ == '__main__':
    unittest.main()
