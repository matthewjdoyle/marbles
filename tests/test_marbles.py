"""Run with: python -m unittest discover -s tests -v"""

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

from demo_shapes import tiled_preview
from marble_circles import MarbleGenerator, MarbleStyle
from marble_shapes import polygon_geometry, polygon_mask, save_png
from random_marble_generator import RandomMarbleGenerator


ROOT = Path(__file__).resolve().parents[1]


def render(shape='rectangle', width=80, height=64, seed=123, **options):
    with redirect_stdout(io.StringIO()):
        return MarbleGenerator(width=width, height=height, seed=seed).generate_marble(
            shape, **options)


class RenderingTests(unittest.TestCase):
    def test_all_styles_and_new_shapes(self):
        for style in MarbleGenerator.MARBLE_STYLES:
            for shape in ('rectangle', 'triangle', 'hexagon'):
                with self.subTest(style=style, shape=shape):
                    image = render(shape, style_name=style)
                    self.assertEqual(image.size, (80, 64))
                    self.assertEqual(image.mode, 'RGBA')
                    self.assertGreater(np.ptp(np.array(image)[..., :3].astype(int)), 0)

    def test_rectangles_are_opaque_in_portrait_and_landscape(self):
        for width, height in ((64, 97), (97, 64), (64, 64)):
            image = render(width=width, height=height, style_name='jupiter')
            self.assertEqual(image.size, (width, height))
            self.assertEqual(image.getchannel('A').getextrema(), (255, 255))

    def test_polygon_transparency_and_antialiasing(self):
        for shape in ('triangle', 'hexagon'):
            image = render(shape, width=97, height=83)
            alpha = np.array(image.getchannel('A'))
            self.assertEqual(alpha[0, 0], 0)
            self.assertEqual(alpha[0, -1], 0)
            self.assertEqual(alpha[41, 48], 255)
            self.assertTrue(np.any((alpha > 0) & (alpha < 255)))
            np.testing.assert_array_equal(alpha, np.array(polygon_mask(shape, 97, 83)))

    def test_regular_geometry_on_nonsquare_canvases(self):
        for shape in ('triangle', 'hexagon'):
            for width, height in ((100, 300), (300, 100), (97, 83)):
                geometry = polygon_geometry(shape, width, height)
                vertices = geometry['vertices']
                for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                    self.assertAlmostEqual(math.dist(a, b), geometry['side'])
                left, top, right, bottom = geometry['bounds']
                self.assertAlmostEqual((left + right) / 2, width / 2)
                self.assertAlmostEqual((top + bottom) / 2, height / 2)
                self.assertGreaterEqual(left, -1e-10)
                self.assertGreaterEqual(top, -1e-10)
                self.assertLessEqual(right, width + 1e-10)
                self.assertLessEqual(bottom, height + 1e-10)
                self.assertTrue(abs(right - left - width) < 1e-8 or
                                abs(bottom - top - height) < 1e-8)

    def test_tessellations_cover_canvas_without_gaps(self):
        white = Image.new('RGBA', (97, 97), 'white')
        for shape in ('triangle', 'hexagon'):
            preview = tiled_preview(shape, [white], size=(413, 297), tile_size=97)
            self.assertEqual(preview.getextrema(), ((255, 255),) * 3)

    def test_seed_repeatability_and_preset_immutability(self):
        before = deepcopy(vars(MarbleGenerator.MARBLE_STYLES['golden']))
        first = render(style_name='golden', intensity=1.8)
        render('hexagon', style_name='golden', intensity=0.3)
        second = render(style_name='golden', intensity=1.8)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(before, vars(MarbleGenerator.MARBLE_STYLES['golden']))
        self.assertNotEqual(first.tobytes(), render(seed=321, style_name='golden', intensity=1.8).tobytes())

    def test_new_shapes_repeat_across_processes(self):
        program = '''
import hashlib, json
from marble_circles import MarbleGenerator
results = []
for style in MarbleGenerator.MARBLE_STYLES:
    image = MarbleGenerator(size=64, seed=42).generate_marble('rectangle', style)
    results.append(hashlib.sha256(image.tobytes()).hexdigest())
print(json.dumps(results))
'''
        first = subprocess.check_output([sys.executable, '-c', program], cwd=ROOT)
        second = subprocess.check_output([sys.executable, '-c', program], cwd=ROOT)
        self.assertEqual(first, second)

    def test_full_custom_style_is_applied_without_mutating_it(self):
        style = MarbleStyle('Test', ['#134455', '#DBBA66', '#EEEEEE'])
        before = deepcopy(vars(style))
        first = render(custom_style=style, intensity=1.8)
        self.assertEqual(before, vars(style))
        style.texture_scale = 2.0
        self.assertNotEqual(first.tobytes(), render(custom_style=style, intensity=1.8).tobytes())

    def test_circle_entry_point_and_default(self):
        with redirect_stdout(io.StringIO()):
            a = MarbleGenerator(size=64, seed=5).generate_marble()
            b = MarbleGenerator(size=64, seed=5).generate_marble_circle()
        self.assertEqual(a.tobytes(), b.tobytes())

    def test_legacy_circle_pixels_in_same_process(self):
        original = ROOT / 'tests/fixtures/original_marble_circles.py'
        spec = importlib.util.spec_from_file_location('legacy_circles', original)
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        cases = json.loads((ROOT / 'tests/fixtures/baselines.json').read_text())
        with redirect_stdout(io.StringIO()):
            for case in cases:
                old = legacy.MarbleGenerator(case['size'], 12345).generate_marble_circle(
                    case['style'], case['colors'], case['intensity'])
                new = MarbleGenerator(case['size'], 12345).generate_marble_circle(
                    case['style'], case['colors'], case['intensity'])
                self.assertEqual(old.tobytes(), new.tobytes(), case['name'])

    def test_invalid_dimensions_shapes_and_palettes(self):
        for options in ({'width': 64}, {'height': 64}, {'size': 63}, {'size': 8193},
                        {'size': 64.5}, {'width': 64, 'height': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                MarbleGenerator(**options)
        for options in ({'shape': 'diamond'}, {'shape': 'circle'},
                        {'intensity': float('nan')}, {'custom_colors': ['#FF0000']},
                        {'custom_colors': ['#xyzxyz', '#000000']}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                render(**options)

    def test_save_does_not_replace_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.png'
            first = save_png(Image.new('RGB', (64, 64), 'red'), path)
            original_bytes = first.read_bytes()
            second = save_png(Image.new('RGB', (64, 64), 'blue'), path)
            self.assertEqual(second.name, 'example_001.png')
            self.assertEqual(first.read_bytes(), original_bytes)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, script, *args, success=True):
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / script), *args],
                                cwd=ROOT, env=env, capture_output=True, text=True,
                                encoding='utf-8')
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_main_shapes_and_non_overwriting_circle(self):
        with tempfile.TemporaryDirectory() as directory:
            for shape in ('circle', 'rectangle', 'triangle', 'hexagon'):
                self.run_cli('marble_circles.py', '--shape', shape, '--size', '64',
                             '--seed', '42', '--output', directory)
            self.run_cli('marble_circles.py', '--size', '64', '--output', directory)
            self.assertEqual(len(list(Path(directory).glob('*.png'))), 5)
            self.assertTrue((Path(directory) / 'marble_circle.png').exists())
            self.assertTrue((Path(directory) / 'marble_circle_001.png').exists())
            self.run_cli('marble_circles.py', '--shape', 'rectangle', '--width', '80',
                         '--height', '64', '--output', directory)
            with Image.open(Path(directory) / 'marble_rectangle_80x64.png') as image:
                self.assertEqual(image.size, (80, 64))

    def test_invalid_cli_dimensions(self):
        for script in ('marble_circles.py', 'random_marble_generator.py'):
            for args in (['--width', '64'], ['--width', '80', '--height', '64'],
                         ['--shape', 'diamond']):
                self.run_cli(script, *args, success=False)
        self.run_cli('random_marble_generator.py', '--shape', 'rectangle', '--sizes', '64',
                     '--width', '80', '--height', '64', success=False)
        self.run_cli('random_marble_generator.py', '--batch-size', '0', success=False)

    def test_random_batch_shapes_and_summary_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / 'batch_summary.txt'
            summary.write_text('Keep this existing summary.')
            for shape in ('circle', 'rectangle', 'triangle', 'hexagon'):
                self.run_cli('random_marble_generator.py', '--shape', shape, '--sizes', '64',
                             '--batch-size', '1', '--seed', '123', '--output', directory)
            self.assertEqual(len(list(Path(directory).glob('*.png'))), 4)
            self.assertEqual(summary.read_text(), 'Keep this existing summary.')
            self.assertEqual(len(list(Path(directory).glob('batch_summary*.txt'))), 5)
            self.run_cli('random_marble_generator.py', '--shape', 'rectangle', '--width', '80',
                         '--height', '64', '--batch-size', '1', '--output', directory)
            paths = list(Path(directory).glob('*rectangle_80x64*.png'))
            self.assertEqual(len(paths), 1)

    def test_parameter_exploration_dimensions_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            for _ in range(2):
                RandomMarbleGenerator(seed=123).generate_parameter_exploration(
                    directory, parameter_steps=2, shape='triangle', width=80, height=64)
            paths = list(Path(directory).glob('*.png'))
            self.assertEqual(len(paths), 20)
            for path in paths:
                with Image.open(path) as image:
                    self.assertEqual(image.size, (80, 64))
                    self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.run_cli('random_marble_generator.py', '--explore-parameters',
                         '--shape', 'hexagon', '--sizes', '64', '--output', directory)


if __name__ == '__main__':
    unittest.main()
