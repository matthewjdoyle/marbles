"""Migration, independent design choices, new geometry, and GUI control behavior."""
from dataclasses import asdict, replace
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PIL import Image

from marbledesk.studio.branding import APP_NAME, icon_path
from marbledesk.studio.model import Design, Document, Composition, PALETTES
from marbledesk.studio.render import render_design, render_composition
from marbledesk.studio.window import StudioWindow


class NewModelTests(unittest.TestCase):
    def test_8k_composition_has_exact_size_and_coverage(self):
        tile = Design(shape='hexagon', width=64, height=64)
        image = render_composition(Composition((tile,), 7680, 4320, 2048))
        self.assertEqual(image.size, (7680, 4320))
        self.assertGreater(image.getextrema()[0][0], 0)

    def test_old_documents_keep_exact_pixels(self):
        for style in ('carrara', 'blue', 'jupiter', 'alien'):
            original = Design.preset(style, shape='rectangle', width=64, height=80, seed=17)
            legacy = asdict(original)
            for key in ('pattern', 'planet_type', 'palette', 'corner_radius', 'star_points', 'star_inner_ratio'):
                legacy.pop(key)
            legacy['style'] = style
            loaded = Document.from_dict({'schema_version': 1, 'design': legacy}).design
            self.assertEqual(original, loaded)
            self.assertEqual(render_design(original).tobytes(), render_design(loaded).tobytes())

    def test_patterns_palettes_and_shapes_roundtrip(self):
        for pattern in ('ribbon_bands', 'concentric_rings', 'cellular_stone'):
            design = replace(Design(), pattern=pattern, shape='star', width=64, height=80,
                             palette='teal_copper', colors=PALETTES['teal_copper'][1],
                             star_points=7, star_inner_ratio=.35)
            self.assertEqual(design, Document.from_dict(Document(design=design).to_dict()).design)
            self.assertNotIn('style', Document(design=design).to_dict()['design'])
            first = render_design(design)
            self.assertEqual(first.size, (64, 80))
            self.assertEqual(first.tobytes(), render_design(design).tobytes())
            self.assertNotEqual(first.tobytes(), render_design(replace(design, seed=18)).tobytes())
            self.assertEqual(first.getpixel((0, 0))[3], 0)
        for shape in ('ellipse', 'rounded_rectangle', 'pentagon', 'octagon'):
            image = render_design(replace(Design(), shape=shape, width=80, height=64))
            self.assertEqual(image.size, (80, 64))
            self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_version_two_planet_patterns_migrate_without_pixel_change(self):
        for planet in ('earth', 'mars', 'jupiter', 'ice_world', 'desert',
                       'volcanic', 'ocean_world', 'alien'):
            original = Design.preset(planet, shape='rectangle', width=64, height=80, seed=31)
            old = asdict(original)
            old['pattern'] = planet
            old.pop('planet_type')
            loaded = Document.from_dict({'schema_version': 2, 'design': old}).design
            self.assertEqual(loaded, original)
            self.assertEqual(render_design(loaded).tobytes(), render_design(original).tobytes())


class NewWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = StudioWindow()
        self.window.debounce.stop()

    def tearDown(self):
        self.window.debounce.stop()
        self.window.jobs.shutdown()
        self.window.confirm_unsaved = lambda: True
        self.window.close()

    def test_palette_pattern_and_canvas_presets_are_independent_and_undoable(self):
        w = self.window
        w.pattern.setCurrentIndex(w.pattern.findData('planetary'))
        w.planet_type.setCurrentIndex(w.planet_type.findData('jupiter'))
        old = w.document.design
        w.palette.setCurrentIndex(w.palette.findData('amethyst'))
        self.assertEqual(w.document.design.pattern, old.pattern)
        self.assertEqual(w.document.design.seed, old.seed)
        self.assertEqual(w.document.design.colors, PALETTES['amethyst'][1])
        w.pattern.setCurrentIndex(w.pattern.findData('ribbon_bands'))
        self.assertEqual(w.document.design.palette, 'amethyst')
        self.assertEqual(w.document.design.colors, PALETTES['amethyst'][1])
        w.pattern.setCurrentIndex(w.pattern.findData('planetary'))
        self.assertEqual(w.document.design.planet_type, 'jupiter')
        before = w.history_index
        w.tile_preset.setCurrentIndex(w.tile_preset.findText('8K UHD'))
        self.assertEqual((w.document.composition.width, w.document.composition.height), (7680, 4320))
        self.assertEqual(w.history_index, before + 1)
        w.undo()
        self.assertEqual((w.document.composition.width, w.document.composition.height), (1920, 1080))

    def test_application_name_and_icon_assets(self):
        self.assertEqual(APP_NAME, 'marbles by MJD')
        self.assertIn(APP_NAME, self.window.windowTitle())
        self.assertFalse(self.window.windowIcon().isNull())
        with Image.open(icon_path()) as icon:
            self.assertEqual(icon.size, (1024, 1024))
            self.assertEqual(icon.getpixel((0, 0))[3], 0)

    def test_wheel_does_not_edit_closed_controls(self):
        w = self.window
        w.show()
        self.app.processEvents()
        scroll = w.tabs.widget(0).verticalScrollBar()
        controls = (w.width, w.controls['intensity'].spin,
                    w.controls['intensity'].slider, w.palette)
        for control in controls:
            scroll.setValue(0)
            before = control.value() if hasattr(control, 'value') else control.currentIndex()
            event = QWheelEvent(QPoint(5, 5), QPoint(5, 5), QPoint(), QPoint(0, -120),
                                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.ScrollUpdate, False)
            QApplication.sendEvent(control, event)
            after = control.value() if hasattr(control, 'value') else control.currentIndex()
            self.assertEqual(before, after)
            self.assertGreater(scroll.value(), 0)

    def test_palette_actions_have_valid_enabled_states_and_single_undo(self):
        w = self.window
        w.palette_list.setCurrentRow(0)
        self.assertFalse(w.color_up.isEnabled())
        self.assertTrue(w.color_down.isEnabled())
        before = w.history_index
        w.color_down.click()
        self.assertEqual(w.history_index, before + 1)
        self.assertEqual(w.palette_list.currentRow(), 1)
        w.undo()
        self.assertEqual(w.document.design.colors, Design().colors)
        while len(w.document.design.colors) > 2:
            w.color_remove.click()
        self.assertFalse(w.color_remove.isEnabled())

    def test_open_palette_wheel_does_not_select(self):
        w = self.window
        w.show()
        self.app.processEvents()
        before = w.palette.currentIndex()
        w.palette.showPopup()
        self.app.processEvents()
        event = QWheelEvent(QPoint(5, 5), QPoint(5, 5), QPoint(), QPoint(0, -120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.ScrollUpdate, False)
        QApplication.sendEvent(w.palette, event)
        self.assertEqual(w.palette.currentIndex(), before)
        QApplication.sendEvent(w.palette.view().viewport(), event)
        self.assertEqual(w.palette.currentIndex(), before)
        w.palette.hidePopup()

    def test_stale_export_restarts_for_current_revision(self):
        w = self.window
        w.update_design(seed=99)
        stale = {'kind': 'design', 'recipe': asdict(Design()),
                 'revision': w.revision - 1, 'export_target': 'target.png'}
        with patch.object(w, 'render_final') as restart:
            w.on_result(-1, stale, {'path': 'old.png'})
        restart.assert_called_once_with(export_target='target.png')
        self.assertFalse(w.final_cache)

    def test_retry_action_names_failed_operation(self):
        w = self.window
        w.error = lambda _: None
        w.on_error(1, {'kind': 'commit', 'target': 'target.png'}, 'disk unavailable')
        self.assertEqual(w.retry_button.text(), 'Retry export')
        w.on_error(2, {'kind': 'design', 'batch_index': 0}, 'worker failed')
        self.assertEqual(w.retry_button.text(), 'Retry batch…')

    def test_palette_button_keyboard_activation_changes_once(self):
        w = self.window
        w.show()
        self.app.processEvents()
        before = w.history_index
        w.color_add.setFocus()
        QTest.keyClick(w.color_add, Qt.Key.Key_Space)
        self.assertEqual(len(w.document.design.colors), 5)
        self.assertEqual(w.history_index, before + 1)

    def test_trackpad_pixel_scroll_moves_panel_without_edit(self):
        w = self.window
        w.show()
        self.app.processEvents()
        scroll = w.tabs.widget(0).verticalScrollBar()
        before = w.width.value()
        event = QWheelEvent(QPoint(5, 5), QPoint(5, 5), QPoint(0, -45), QPoint(),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.ScrollUpdate, False)
        QApplication.sendEvent(w.width, event)
        self.assertEqual(w.width.value(), before)
        self.assertGreater(scroll.value(), 0)


if __name__ == '__main__':
    unittest.main()
