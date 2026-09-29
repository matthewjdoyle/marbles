"""Core studio invariants; runnable without Qt."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from marbledesk.studio.model import Design, Document, Composition, BatchSettings, batch_recipes, SCHEMES
from marbledesk.studio.render import render_design, render_composition
from marbledesk.studio.storage import atomic_write, save_json, save_image


class DocumentTests(unittest.TestCase):
    def test_roundtrip_full_document(self):
        tile = Design.preset('jupiter', shape='hexagon', width=64, height=80)
        document = Document(tile, BatchSettings(sizes=((64, 64), (128, 96))),
                            Composition((tile, replace(tile, seed=90)), 128, 96, 64), True)
        with tempfile.TemporaryDirectory() as directory:
            path = save_json(Path(directory) / 'design.json', document.to_dict())
            self.assertEqual(document, Document.load(path))
            self.assertEqual(render_composition(document.composition).tobytes(),
                             render_composition(Document.load(path).composition).tobytes())

    def test_reject_invalid_inputs(self):
        for changes in ({'width': True}, {'seed': -1}, {'seed': 2**31}, {'complexity': 2.5},
                        {'colors': ['#FFFFFF']}, {'colors': ['bad', '#112233']},
                        {'shape': 'diamond'}, {'height': 64}, {'texture_scale': float('nan')},
                        {'renderer_version': 'future'}, {'vein_scale': 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Design(), **changes)
        with self.assertRaises(ValueError):
            Document.from_dict({'schema_version': 99})
        with self.assertRaises(ValueError):
            Composition((Design(shape='triangle'), Design(shape='hexagon')))
        with self.assertRaises(ValueError):
            BatchSettings(sizes=((64,),))
        with self.assertRaises(ValueError):
            BatchSettings(palette='yes')

    def test_batches_have_private_rng_and_reproducible_recipes(self):
        original = random.getstate()
        design = Design.preset('alien', shape='triangle', width=64, height=64)
        settings = BatchSettings(count=3, palette=True, texture=True, sizes=((64, 64), (80, 96)))
        first = batch_recipes(design, settings)
        self.assertEqual(random.getstate(), original)
        render_design(first[0])  # Rendering mutates legacy global random state.
        self.assertEqual(first, batch_recipes(design, settings))
        self.assertEqual(len(first), 6)
        default = batch_recipes(design, BatchSettings(count=2))
        self.assertEqual(replace(default[0], seed=design.seed), design)
        for scheme in SCHEMES:
            self.assertEqual(len(batch_recipes(design, BatchSettings(count=1, palette=True, scheme=scheme))[0].colors), 5)


class StudioRenderTests(unittest.TestCase):
    def test_circle_is_stable_across_processes(self):
        program = '''
import hashlib,json
from marbledesk.studio.model import Design
from marbledesk.studio.render import render_design
from marble_circles import MarbleGenerator
print(json.dumps([hashlib.sha256(render_design(Design.preset(s,width=64,height=64)).tobytes()).hexdigest() for s in MarbleGenerator.MARBLE_STYLES]))
'''
        a = subprocess.check_output([sys.executable, '-c', program])
        b = subprocess.check_output([sys.executable, '-c', program])
        self.assertEqual(a, b)

    def test_all_texture_parameters_apply_to_circle(self):
        design = Design.preset('blue', width=80, height=80)
        baseline = render_design(design).tobytes()
        for name, value in [('intensity', 2), ('vein_intensity', 1.2), ('vein_scale', .030),
                            ('complexity', 5), ('texture_scale', 2), ('seed', 123),
                            ('colors', ('#000000', '#FF0000'))]:
            with self.subTest(name=name):
                self.assertNotEqual(baseline, render_design(replace(design, **{name: value})).tobytes())

    def test_renderer_always_returns_exact_dimensions(self):
        design = Design(shape='rectangle', width=640, height=128)
        image = render_design(design)
        self.assertEqual(image.size, (640, 128))
        self.assertEqual(render_design(replace(design, width=80, height=64)).size, (80, 64))

    def test_tiling_order_changes_output_and_preserves_coverage(self):
        a = Design.preset('blue', shape='hexagon', width=64, height=64)
        b = Design.preset('golden', shape='hexagon', width=64, height=64)
        image = render_composition(Composition((a, b), 160, 128, 64))
        reverse = render_composition(Composition((b, a), 160, 128, 64))
        self.assertEqual(image.size, (160, 128))
        self.assertEqual(image.mode, 'RGB')
        self.assertNotEqual(image.tobytes(), reverse.tobytes())
        self.assertGreater(image.convert('L').getextrema()[0], 0)


class StorageTests(unittest.TestCase):
    def test_failed_write_leaves_no_partial_or_replaced_file(self):
        def fail(stream):
            stream.write(b'partial image')
            raise OSError('simulated disk failure')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.png'
            save_image(path, Image.new('RGB', (64, 64), 'red'))
            before = path.read_bytes()
            with self.assertRaises(OSError):
                atomic_write(path, fail)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            other = save_image(path, Image.new('RGB', (64, 64), 'blue'))
            self.assertEqual(other.name, 'image_001.png')
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
