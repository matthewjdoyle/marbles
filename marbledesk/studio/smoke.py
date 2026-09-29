"""End-to-end Qt/worker check, also runnable inside the packaged application."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
import traceback
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QFontDatabase, QFont
from PySide6.QtWidgets import QFileDialog, QDialog, QListWidget

from .model import Design, Document
from .render import render_design, render_composition


def run_smoke(application, window):
    # The Windows offscreen plugin does not discover installed system fonts.
    # Load the system UI face explicitly for headless screenshot inspection.
    if os.name == 'nt' and os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            application.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))
    errors = []
    window.error = errors.append

    def wait_for(predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while not predicate():
            application.processEvents()
            if errors:
                raise AssertionError(errors)
            if time.monotonic() > deadline:
                raise TimeoutError('GUI smoke test timed out')
            time.sleep(.01)
        application.processEvents()
        if errors:
            raise AssertionError(errors)

    try:
        with tempfile.TemporaryDirectory(prefix='marble-smoke-') as directory:
            folder = Path(directory)
            window.debounce.stop()
            window.shape.setCurrentIndex(window.shape.findData('triangle'))
            window.width.setValue(64)
            window.height.setValue(64)
            window.palette.setCurrentIndex(window.palette.findData('blue'))
            window.controls['texture_scale'].spin.setValue(1.5)
            assert window.document.design.texture_scale == 1.5
            window.undo()
            assert window.document.design.texture_scale == 1
            window.redo()
            assert window.document.design.texture_scale == 1.5
            window.seed_lock.setChecked(True)
            assert not window.variation_button.isEnabled()
            window.seed_lock.setChecked(False)
            window.render_final()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            key = window.request_key(window.current_request())
            expected = render_design(window.document.design)
            with Image.open(window.final_cache[key]) as rendered:
                assert rendered.tobytes() == expected.tobytes()
            png = folder / 'export.png'
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(png), '')):
                window.export_png()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            with Image.open(png) as exported:
                assert exported.tobytes() == expected.tobytes()

            # Collision-safe export reuses exactly the inspected final image.
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(png), '')):
                window.export_png()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            assert (folder / 'export_001.png').exists()

            # A superseded final render cannot overwrite the current preview/cache.
            old_revision = window.revision
            old_request = dict(window.current_request(), revision=old_revision)
            window.update_design(seed=123)
            window.on_result(-1, old_request, {'path': str(png)})
            assert not window.final_cache

            window.tabs.setCurrentIndex(1)
            window.batch_count.setValue(2)
            with patch.object(QFileDialog, 'getExistingDirectory', return_value=str(folder)):
                window.start_batch()
            wait_for(lambda: window.batch_run is None, timeout=90)
            manifest = json.loads(next(folder.glob('batch_*.json')).read_text())
            assert all(entry['status'] == 'complete' for entry in manifest['entries'])
            assert '2 images saved' in window.batch_summary.text()
            if os.environ.get('MARBLE_SMOKE_OUTPUT'):
                screenshots = Path(os.environ['MARBLE_SMOKE_OUTPUT'])
                screenshots.mkdir(parents=True, exist_ok=True)
                application.processEvents()
                window.grab().save(str(screenshots / 'batch.png'))
            def select_batch(dialog):
                choices = dialog.findChild(QListWidget)
                for index in range(choices.count()):
                    choices.item(index).setSelected(True)
                return QDialog.DialogCode.Accepted
            with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(next(folder.glob('batch_*.json'))), '')):
                with patch.object(QDialog, 'exec', select_batch):
                    window.add_tiles_from_batch()
            assert len(window.document.composition.tiles) == 2
            window.tile_width.setValue(128)
            window.tile_height.setValue(96)
            window.tile_size.setValue(64)
            window.render_final()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            key = window.request_key(window.current_request())
            with Image.open(window.final_cache[key]) as actual:
                assert actual.tobytes() == render_composition(window.document.composition).tobytes()
            if os.environ.get('MARBLE_SMOKE_OUTPUT'):
                application.processEvents()
                window.grab().save(str(Path(os.environ['MARBLE_SMOKE_OUTPUT']) / 'tiling.png'))

            document = folder / 'saved.json'
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(document), '')):
                assert window.save_document()
            saved = window.document
            window.update_design(seed=999)
            window.confirm_unsaved = lambda: True
            with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(document), '')):
                window.open_document()
            assert window.document == saved == Document.load(document)

            # Real cancellation of a large spawned job followed by successful work.
            window.tabs.setCurrentIndex(0)
            window.update_design(width=2048, height=2048)
            window.render_final()
            application.processEvents()
            window.cancel_jobs()
            assert not window.jobs.busy
            window.update_design(width=64, height=64)
            window.render_final()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)

            # Completed batch files survive cancellation; remaining recipes stay
            # in the manifest with an explicit cancelled status.
            window.batch_count.setValue(3)
            cancelled_folder = folder / 'cancelled-batch'
            cancelled_folder.mkdir()
            with patch.object(QFileDialog, 'getExistingDirectory', return_value=str(cancelled_folder)):
                window.start_batch()
            wait_for(lambda: window.batch_run and window.batch_run['index'] >= 1)
            window.cancel_jobs()
            wait_for(lambda: not window.jobs.busy and window.batch_run is None)
            cancelled_manifest = json.loads(next(cancelled_folder.glob('batch_*.json')).read_text())
            assert cancelled_manifest['entries'][0]['status'] == 'complete'
            assert all(entry['status'] == 'cancelled' for entry in cancelled_manifest['entries'][1:])
            assert len(list(cancelled_folder.glob('*.png'))) == 1

            # Superseded automatic renders are rejected even if a delayed result arrives.
            request = dict(window.current_request(), interactive=True, revision=window.revision - 1)
            window.latest_render = 987654
            before_state = window.preview_state.text()
            window.on_result(987654, request, {'path': 'does-not-exist.png'})
            assert window.preview_state.text() == before_state

            # Worker failure is surfaced and a subsequent request still succeeds.
            window.jobs.submit({'kind': 'design', 'recipe': {'style': 'unknown'}, 'revision': window.revision})
            deadline = time.monotonic() + 15
            while not errors and time.monotonic() < deadline:
                application.processEvents()
                time.sleep(.01)
            assert errors and 'Unknown pattern family' in errors[-1]
            errors.clear()
            window.render_final()
            wait_for(lambda: not window.jobs.busy and not window.export_pending)

            # Automatic renders use export dimensions too, never a lower-res
            # approximation. Rapid edits cancel the previous request.
            window.update_design(shape='rectangle', width=320, height=96)
            window.request_render()
            window.update_design(seed=808)
            key = window.request_key(window.current_request())
            wait_for(lambda: key in window.final_cache and not window.jobs.busy)
            with Image.open(window.final_cache[key]) as actual:
                assert actual.size == (320, 96)
                assert actual.tobytes() == render_design(window.document.design).tobytes()
            window.update_design(seed=909)
            window.request_render()
            active_id = window.jobs.active[0]
            window.render_final()
            assert window.jobs.active[0] == active_id, 'Do not restart an exact render already in progress'
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            window.update_design(seed=1010)
            window.request_render()
            active_id = window.jobs.active[0]
            promoted_export = folder / 'in-progress-export.png'
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(promoted_export), '')):
                window.export_png()
            assert window.jobs.active[0] == active_id, 'Export should reuse the running exact render'
            wait_for(lambda: not window.jobs.busy and not window.export_pending)
            with Image.open(promoted_export) as actual:
                assert actual.tobytes() == render_design(window.document.design).tobytes()

            output = os.environ.get('MARBLE_SMOKE_OUTPUT')
            if output:
                screenshots = Path(output)
                screenshots.mkdir(parents=True, exist_ok=True)
                window.update_design(width=512, height=512)
                window.tabs.setCurrentIndex(0)
                window.pattern.setCurrentIndex(window.pattern.findData('planetary'))
                window.planet_type.setCurrentIndex(window.planet_type.findData('jupiter'))
                window.palette.setCurrentIndex(window.palette.findData('jupiter'))
                window.shape.setCurrentIndex(window.shape.findData('circle'))
                window.debounce.stop()
                window.render_final()
                wait_for(lambda: not window.jobs.busy and not window.export_pending)
                original_palette = application.palette()
                for name, dark in [('light', False), ('dark', True)]:
                    palette = QPalette()
                    for role, color in {
                        QPalette.ColorRole.Window: '#252A31' if dark else '#F3F5F8',
                        QPalette.ColorRole.WindowText: '#EEF2F7' if dark else '#182333',
                        QPalette.ColorRole.Base: '#30363F' if dark else '#FFFFFF',
                        QPalette.ColorRole.Text: '#EEF2F7' if dark else '#182333',
                        QPalette.ColorRole.Button: '#30363F' if dark else '#F3F5F8',
                        QPalette.ColorRole.ButtonText: '#EEF2F7' if dark else '#182333',
                        QPalette.ColorRole.Highlight: '#559DEB',
                        QPalette.ColorRole.HighlightedText: '#FFFFFF',
                    }.items():
                        palette.setColor(role, QColor(color))
                    application.setPalette(palette)
                    window.apply_theme()
                    application.processEvents()
                    window.grab().save(str(screenshots / f'studio-{name}.png'))
                application.setPalette(original_palette)
            window.debounce.stop()
            window.jobs.shutdown()
        print('marbles by MJD smoke test passed: edit, undo/redo, seed lock, render, export, batch, tiling, save/open, cancel, recovery.')
        if os.environ.get('MARBLE_SMOKE_OUTPUT'):
            Path(os.environ['MARBLE_SMOKE_OUTPUT'], 'smoke-result.json').write_text(
                json.dumps({'passed': True, 'platform': os.name}), encoding='utf-8')
        return 0
    except BaseException:
        traceback.print_exc()
        if os.environ.get('MARBLE_SMOKE_OUTPUT'):
            output = Path(os.environ['MARBLE_SMOKE_OUTPUT'])
            output.mkdir(parents=True, exist_ok=True)
            (output / 'smoke-result.json').write_text(
                json.dumps({'passed': False, 'traceback': traceback.format_exc()}), encoding='utf-8')
        window.jobs.shutdown()
        return 1
