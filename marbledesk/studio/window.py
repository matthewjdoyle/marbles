"""marbles by MJD's three connected workspaces."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import secrets
import time
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QColorDialog,
    QScrollArea, QSplitter, QTabWidget, QFormLayout, QLineEdit, QProgressBar,
    QDialog, QDialogButtonBox,
)

from marble_circles import MarbleGenerator
from marble_shapes import SHAPES
from .jobs import RenderQueue
from .branding import APP_NAME, icon_path
from .model import Design, Document, BatchSettings, Composition, RANGES, SCHEMES, PATTERNS, PLANET_TYPES, PALETTES, batch_recipes
from .storage import save_json
from .widgets import (Section, NumberControl, Preview, NoWheelComboBox,
                      NoWheelSpinBox, NoWheelDoubleSpinBox)

CANVAS_PRESETS = [('Custom', None), ('HD', (1280, 720)), ('Full HD', (1920, 1080)),
                  ('QHD', (2560, 1440)), ('4K UHD', (3840, 2160)),
                  ('8K UHD', (7680, 4320)), ('Phone portrait', (1080, 1920))] + [
                      (f'Square {side}', (side, side)) for side in (512, 1024, 2048, 4096, 8192)]


LABELS = {'intensity': 'Overall intensity', 'vein_intensity': 'Vein strength',
          'vein_scale': 'Vein frequency', 'complexity': 'Complexity', 'texture_scale': 'Texture frequency'}
HELP = {'intensity': 'Multiplies vein strength without changing the palette.',
        'vein_intensity': 'Controls how strongly veins lighten and darken the surface.',
        'vein_scale': 'Higher values create finer, more frequent veins.',
        'complexity': 'Number of noise layers. More layers add fine detail.',
        'texture_scale': 'Higher values make texture elements smaller.'}


def button(label, callback):
    widget = QPushButton(label)
    widget.clicked.connect(callback)
    widget.setAccessibleName(label)
    widget.setToolTip(label)
    if label in ('+', '−', '↑', '↓'):
        widget.setMinimumWidth(40)
        widget.setMinimumHeight(34)
        widget.setToolTip({'+': 'Add', '−': 'Remove', '↑': 'Move up', '↓': 'Move down'}[label])
        widget.setAccessibleName(widget.toolTip())
    return widget


def spin(low=64, high=8192):
    widget = NoWheelSpinBox()
    widget.setRange(low, high)
    widget.setKeyboardTracking(False)
    return widget


def row(*widgets):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return container


def form_row(layout, label, widget):
    caption = QLabel(label)
    caption.setBuddy(widget)
    widget.setAccessibleName(label)
    layout.addRow(caption, widget)


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document = Document()
        self.saved_document = self.document.to_dict()
        self.document_path = None
        self.history = [self.document]
        self.history_index = 0
        self.last_edit = ('', 0)
        self.loading = False
        self.revision = 0
        self.final_cache = {}
        self.latest_render = None
        self.batch_run = None
        self.export_pending = False
        self.failed_request = None
        self.close_after_save = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(1240, 850)
        self.setMinimumSize(880, 640)
        self.jobs = RenderQueue(self)
        self.jobs.result.connect(self.on_result)
        self.jobs.failed.connect(self.on_error)
        self.jobs.progress.connect(self.show_progress)
        self.jobs.busy_changed.connect(self.busy_changed)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(300)
        self.debounce.timeout.connect(self.request_render)
        self.build_ui()
        self.load_widgets()
        self.apply_theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        self.debounce.start()

    def build_ui(self):
        toolbar = self.addToolBar('Document')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for title, shortcut, callback in [('Open…', QKeySequence.StandardKey.Open, self.open_document),
                                           ('Save', QKeySequence.StandardKey.Save, self.save_document)]:
            action = QAction(title, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            toolbar.addAction(action)
        save_as = QAction('Save as…', self)
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as.triggered.connect(lambda: self.save_document(save_as=True))
        toolbar.addAction(save_as)
        toolbar.addSeparator()
        self.undo_action = QAction('Undo', self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)
        toolbar.addAction(self.undo_action)
        self.redo_action = QAction('Redo', self)
        self.redo_action.setShortcuts([QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence('Ctrl+Shift+Z')])
        self.redo_action.triggered.connect(self.redo)
        toolbar.addAction(self.redo_action)
        spacer = QWidget()
        from PySide6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.export_button = button('Export PNG…', self.export_png)
        self.export_button.setObjectName('primary')
        toolbar.addWidget(self.export_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(340)
        self.tabs.setMaximumWidth(470)
        self.tabs.setDocumentMode(True)
        self.studio_layout = self.add_tab('Studio')
        self.batch_layout = self.add_tab('Batch')
        self.tiling_layout = self.add_tab('Tiling')
        self.build_studio()
        self.build_batch()
        self.build_tiling()
        self.tabs.currentChanged.connect(self.workspace_changed)
        splitter.addWidget(self.tabs)

        right = QWidget()
        canvas_layout = QVBoxLayout(right)
        canvas_layout.setContentsMargins(18, 12, 18, 12)
        canvas_layout.setSpacing(10)
        self.preview_title = QLabel('Carrara White')
        self.preview_title.setObjectName('previewTitle')
        self.preview_state = QLabel('Rendering full-resolution image…')
        self.preview_state.setWordWrap(True)
        canvas_layout.addWidget(self.preview_title)
        canvas_layout.addWidget(self.preview_state)
        self.retry_button = button('Retry render', self.retry_render)
        self.retry_button.setVisible(False)
        canvas_layout.addWidget(self.retry_button)
        self.preview = Preview()
        canvas_layout.addWidget(self.preview, 1)
        zoom_out = button('−', lambda: self.preview.zoom(1 / 1.25))
        zoom_in = button('+', lambda: self.preview.zoom(1.25))
        for control, name in ((zoom_out, 'Zoom out'), (zoom_in, 'Zoom in')):
            control.setToolTip(name)
            control.setAccessibleName(name)
        canvas_layout.addWidget(row(button('Fit', self.preview.fit), button('100%', self.preview.actual), zoom_out, zoom_in))
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([370, 870])
        self.setCentralWidget(splitter)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(170)
        self.progress.setVisible(False)
        self.cancel_button = button('Cancel', self.cancel_jobs)
        self.cancel_button.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().addPermanentWidget(self.cancel_button)
        self.statusBar().showMessage('Ready')

    def add_tab(self, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        scroll.setWidget(panel)
        self.tabs.addTab(scroll, title)
        return layout

    def build_studio(self):
        section = Section('Pattern and colors')
        self.pattern = NoWheelComboBox()
        self.pattern.setMaxVisibleItems(10)
        for key, label in PATTERNS.items():
            self.pattern.addItem(label, key)
        self.pattern.currentIndexChanged.connect(self.pattern_changed)
        form = QFormLayout()
        self.pattern_form = form
        form_row(form, 'Pattern', self.pattern)
        self.planet_type = NoWheelComboBox()
        for key, label in PLANET_TYPES.items():
            self.planet_type.addItem(label, key)
        self.planet_type.currentIndexChanged.connect(self.planet_type_changed)
        form_row(form, 'Planet type', self.planet_type)
        self.palette = NoWheelComboBox()
        self.palette.setMaxVisibleItems(10)
        for key, (label, _) in PALETTES.items():
            self.palette.addItem(label, key)
        self.palette.currentIndexChanged.connect(self.palette_changed)
        form_row(form, 'Color palette', self.palette)
        section.content.addLayout(form)
        self.palette_list = QListWidget()
        self.palette_list.setMaximumHeight(160)
        self.palette_list.setAccessibleName('Ordered color palette. Double-click a color to edit its hex value.')
        self.palette_list.itemChanged.connect(self.palette_edited)
        section.content.addWidget(self.palette_list)
        self.color_add = button('+', self.add_color)
        self.color_remove = button('−', self.remove_color)
        self.color_up = button('↑', lambda: self.move_color(-1))
        self.color_down = button('↓', lambda: self.move_color(1))
        for control, name in ((self.color_add, 'Add palette color'),
                              (self.color_remove, 'Remove selected palette color'),
                              (self.color_up, 'Move selected color up'),
                              (self.color_down, 'Move selected color down')):
            control.setAccessibleName(name)
            control.setToolTip(name)
        self.palette_list.currentRowChanged.connect(self.update_palette_buttons)
        self.color_choose = button('Color…', self.choose_color)
        section.content.addWidget(row(self.color_choose, self.color_add,
                                      self.color_remove, self.color_up, self.color_down))
        section.content.addWidget(row(button('Reset pattern settings', self.reset_pattern),
                                      button('Reset palette', self.reset_palette)))
        self.studio_layout.addWidget(section)

        section = Section('Shape and size')
        form = QFormLayout()
        self.shape_form = form
        self.shape = NoWheelComboBox()
        for s in SHAPES:
            self.shape.addItem(s.title(), s)
        self.shape.currentIndexChanged.connect(self.shape_changed)
        form_row(form, 'Shape', self.shape)
        self.size_preset = NoWheelComboBox()
        for label, size in CANVAS_PRESETS:
            self.size_preset.addItem(label, size)
        self.size_preset.currentIndexChanged.connect(self.size_preset_changed)
        form_row(form, 'Canvas preset', self.size_preset)
        self.width, self.height = spin(), spin()
        self.width.valueChanged.connect(lambda v: self.dimension_changed('width', v))
        self.height.valueChanged.connect(lambda v: self.dimension_changed('height', v))
        form_row(form, 'Width, px', self.width)
        form_row(form, 'Height, px', self.height)
        self.swap_button = button('Swap width and height', self.swap_dimensions)
        form.addRow('', self.swap_button)
        self.corner_radius = NoWheelDoubleSpinBox()
        self.corner_radius.setRange(0, .5)
        self.corner_radius.setSingleStep(.01)
        self.corner_radius.valueChanged.connect(lambda value: self.update_design('corner_radius', corner_radius=value))
        form_row(form, 'Corner radius ratio', self.corner_radius)
        self.star_points = spin(3, 16)
        self.star_points.valueChanged.connect(lambda value: self.update_design('star_points', star_points=value))
        form_row(form, 'Star points', self.star_points)
        self.star_inner_ratio = NoWheelDoubleSpinBox()
        self.star_inner_ratio.setRange(.1, .9)
        self.star_inner_ratio.setSingleStep(.01)
        self.star_inner_ratio.valueChanged.connect(lambda value: self.update_design('star_inner_ratio', star_inner_ratio=value))
        form_row(form, 'Star inner radius ratio', self.star_inner_ratio)
        section.content.addLayout(form)
        self.studio_layout.addWidget(section)

        section = Section('Texture')
        self.controls = {}
        self.texture_labels = {}
        for name in ('intensity', 'vein_intensity', 'texture_scale'):
            self.add_texture_control(section.content, name)
        advanced = Section('Fine detail and seed', expanded=False)
        for name in ('vein_scale', 'complexity'):
            self.add_texture_control(advanced.content, name)
        self.seed = spin(0, 2**31 - 1)
        self.seed.valueChanged.connect(lambda v: self.update_design('seed', seed=v))
        form = QFormLayout()
        form_row(form, 'Seed', self.seed)
        advanced.content.addLayout(form)
        self.seed_lock = QCheckBox('Lock seed for new variations')
        self.seed_lock.toggled.connect(lambda v: self.change_document(replace(self.document, seed_locked=v), 'seed_lock'))
        advanced.content.addWidget(self.seed_lock)
        section.content.addWidget(advanced)
        self.variation_button = button('New variation', self.new_variation)
        section.content.addWidget(self.variation_button)
        self.studio_layout.addWidget(section)
        self.studio_layout.addStretch()

    def add_texture_control(self, layout, name):
        label = QLabel(LABELS[name])
        self.texture_labels[name] = label
        decimals, step = (0, 1) if name == 'complexity' else ((3, .001) if name == 'vein_scale' else (2, .01))
        control = NumberControl(*RANGES[name], decimals=decimals, step=step, name=LABELS[name])
        label.setBuddy(control.spin)
        control.setToolTip(HELP[name])
        control.changed.connect(lambda value, key=name, widget=control:
                                self.update_design(key if widget.slider.isSliderDown() else '', **{key: value}))
        layout.addWidget(label)
        layout.addWidget(control)
        self.controls[name] = control

    def build_batch(self):
        intro = QLabel('Explore variations of your Studio design. Each result keeps its own editable recipe.')
        intro.setWordWrap(True)
        self.batch_layout.addWidget(intro)
        form = QFormLayout()
        self.batch_count = spin(1, 1000)
        self.batch_count.valueChanged.connect(self.batch_settings_changed)
        form_row(form, 'Images per size', self.batch_count)
        self.batch_sizes = QLineEdit()
        self.batch_sizes.setPlaceholderText('Current size, or 512x512, 1920x1080')
        self.batch_sizes.setToolTip('Comma-separated WIDTHxHEIGHT pairs. Leave blank to use the Studio canvas.')
        self.batch_sizes.editingFinished.connect(self.batch_settings_changed)
        form_row(form, 'Output sizes', self.batch_sizes)
        self.batch_layout.addLayout(form)
        self.vary_palette = QCheckBox('Vary the color palette')
        self.vary_texture = QCheckBox('Vary texture parameters')
        self.vary_palette.toggled.connect(self.batch_settings_changed)
        self.vary_texture.toggled.connect(self.batch_settings_changed)
        self.batch_layout.addWidget(self.vary_palette)
        self.scheme = NoWheelComboBox()
        self.scheme.addItems([s.title() for s in SCHEMES])
        self.scheme.setAccessibleName('Random palette color scheme')
        self.scheme.currentIndexChanged.connect(self.batch_settings_changed)
        self.batch_layout.addWidget(self.scheme)
        self.batch_layout.addWidget(self.vary_texture)
        ranges_section = Section('Variation ranges', expanded=False)
        ranges_form = QFormLayout()
        self.range_controls = {}
        for name, (low, high) in RANGES.items():
            controls = []
            for _ in range(2):
                control = NoWheelSpinBox() if name == 'complexity' else NoWheelDoubleSpinBox()
                if name != 'complexity':
                    control.setDecimals(3 if name == 'vein_scale' else 2)
                    control.setSingleStep(.001 if name == 'vein_scale' else .01)
                control.setRange(low, high)
                control.setKeyboardTracking(False)
                control.valueChanged.connect(self.batch_settings_changed)
                controls.append(control)
            controls[0].setAccessibleName(LABELS[name] + ' minimum')
            controls[1].setAccessibleName(LABELS[name] + ' maximum')
            self.range_controls[name] = controls
            ranges_form.addRow(LABELS[name], row(controls[0], QLabel('to'), controls[1]))
        ranges_section.content.addLayout(ranges_form)
        self.batch_layout.addWidget(ranges_section)
        note = QLabel('The Studio seed reproduces the entire batch. Seed lock affects single variations only.')
        note.setWordWrap(True)
        self.batch_layout.addWidget(note)
        self.batch_button = button('Generate batch…', self.start_batch)
        self.batch_button.setObjectName('primary')
        self.batch_layout.addWidget(self.batch_button)
        self.batch_summary = QLabel('No batch generated yet.')
        self.batch_summary.setWordWrap(True)
        self.batch_layout.addWidget(self.batch_summary)
        self.batch_layout.addStretch()

    def build_tiling(self):
        intro = QLabel('Repeat generated triangles or hexagons into a wallpaper. Shapes fit together; marble veins may not match at tile edges.')
        intro.setWordWrap(True)
        self.tiling_layout.addWidget(intro)
        self.tile_list = QListWidget()
        self.tile_list.setAccessibleName('Ordered tile designs')
        self.tile_list.setMinimumHeight(150)
        self.tiling_layout.addWidget(self.tile_list)
        self.add_studio_tile_button = button('Add Studio design', self.add_studio_tile)
        self.tiling_layout.addWidget(self.add_studio_tile_button)
        self.tiling_layout.addWidget(button('Add tiles from batch…', self.add_tiles_from_batch))
        self.tile_remove = button('Remove', self.remove_tile)
        self.tile_up = button('↑', lambda: self.move_tile(-1))
        self.tile_down = button('↓', lambda: self.move_tile(1))
        for control, name in ((self.tile_up, 'Move selected tile up'),
                              (self.tile_down, 'Move selected tile down')):
            control.setAccessibleName(name)
            control.setToolTip(name)
        self.tile_list.currentRowChanged.connect(self.update_tile_buttons)
        self.tiling_layout.addWidget(row(self.tile_remove, self.tile_up, self.tile_down))
        form = QFormLayout()
        self.tile_width, self.tile_height, self.tile_size = spin(), spin(), spin(64, 2048)
        self.tile_preset = NoWheelComboBox()
        for label, size in CANVAS_PRESETS:
            self.tile_preset.addItem(label, size)
        self.tile_preset.currentIndexChanged.connect(self.tile_preset_changed)
        form_row(form, 'Canvas preset', self.tile_preset)
        form_row(form, 'Wallpaper width, px', self.tile_width)
        form_row(form, 'Wallpaper height, px', self.tile_height)
        self.tile_swap_button = button('Swap width and height', self.swap_tile_dimensions)
        form.addRow('', self.tile_swap_button)
        form_row(form, 'Tile canvas size, px', self.tile_size)
        self.tile_size.setToolTip('Size of the square tile canvas used for placement. Transparent polygon margins are accounted for automatically.')
        for widget in (self.tile_width, self.tile_height, self.tile_size):
            widget.valueChanged.connect(self.composition_settings_changed)
        self.tiling_layout.addLayout(form)
        self.tiling_layout.addStretch()

    def apply_theme(self):
        dark = QApplication.instance().palette().window().color().lightness() < 128
        border, accent = ('#59616C', '#82B5FA') if dark else ('#B7C1CE', '#225EA8')
        self.setStyleSheet(f'''
            QToolBar {{ padding: 8px; spacing: 8px; border-bottom: 1px solid {border}; }}
            QPushButton {{ padding: 7px 10px; }}
            QPushButton#primary {{ background: {accent}; color: {'#142239' if dark else '#FFFFFF'}; border: none; border-radius: 5px; font-weight: 600; }}
            QPushButton:focus, QToolButton:focus {{ border: 2px solid {accent}; }}
            QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{ padding: 5px; }}
            QTabBar::tab {{ padding: 12px 18px; }}
            QLabel#previewTitle {{ font-size: 22px; font-weight: 600; }}
            QStatusBar {{ padding: 4px; }}
        ''')
        self.preview.viewport().update()

    def load_widgets(self):
        self.loading = True
        d, b, c = self.document.design, self.document.batch, self.document.composition
        self.pattern.setCurrentIndex(self.pattern.findData(d.pattern))
        self.planet_type.setCurrentIndex(self.planet_type.findData(d.planet_type))
        self.planet_type.setVisible(d.pattern == 'planetary')
        self.pattern_form.labelForField(self.planet_type).setVisible(d.pattern == 'planetary')
        self.palette.setCurrentIndex(self.palette.findData(d.palette))
        selection = self.palette_list.currentRow()
        if tuple(self.palette_list.item(i).text() for i in range(self.palette_list.count())) != d.colors:
            self.palette_list.clear()
            for color in d.colors:
                pixmap = QPixmap(24, 24)
                pixmap.fill(QColor(color))
                item = QListWidgetItem(QIcon(pixmap), color)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.palette_list.addItem(item)
            self.palette_list.setCurrentRow(max(0, min(selection, len(d.colors) - 1)))
        self.update_palette_buttons()
        self.shape.setCurrentIndex(self.shape.findData(d.shape))
        self.width.setValue(d.width)
        self.height.setValue(d.height)
        self.height.setEnabled(d.shape != 'circle')
        self.swap_button.setEnabled(d.width != d.height and d.shape != 'circle')
        self.corner_radius.setValue(d.corner_radius)
        self.star_points.setValue(d.star_points)
        self.star_inner_ratio.setValue(d.star_inner_ratio)
        for control, visible in ((self.corner_radius, d.shape == 'rounded_rectangle'),
                                 (self.star_points, d.shape == 'star'),
                                 (self.star_inner_ratio, d.shape == 'star')):
            control.setVisible(visible)
            self.shape_form.labelForField(control).setVisible(visible)
        self.size_preset.setCurrentIndex(0)
        for i in range(1, self.size_preset.count()):
            if self.size_preset.itemData(i) == (d.width, d.height):
                self.size_preset.setCurrentIndex(i)
        for name, control in self.controls.items():
            control.setValue(getattr(d, name))
        complexity_visible = d.pattern not in ('ribbon_bands', 'concentric_rings', 'cellular_stone')
        self.controls['complexity'].setVisible(complexity_visible)
        self.texture_labels['complexity'].setVisible(complexity_visible)
        self.seed.setValue(d.seed)
        self.seed_lock.setChecked(self.document.seed_locked)
        self.variation_button.setEnabled(not self.document.seed_locked)
        self.batch_count.setValue(b.count)
        if not self.batch_sizes.hasFocus():
            self.batch_sizes.setText(', '.join(f'{w}x{h}' for w, h in b.sizes))
        self.vary_palette.setChecked(b.palette)
        self.vary_texture.setChecked(b.texture)
        self.scheme.setCurrentIndex(SCHEMES.index(b.scheme))
        self.scheme.setEnabled(b.palette)
        for name, widgets in self.range_controls.items():
            for widget, value in zip(widgets, b.ranges[name]):
                widget.setValue(value)
                widget.setEnabled(b.texture)
        selection = self.tile_list.currentRow()
        self.tile_list.clear()
        for i, tile in enumerate(c.tiles):
            pattern_label = PLANET_TYPES[tile.planet_type] if tile.pattern == 'planetary' else PATTERNS[tile.pattern]
            self.tile_list.addItem(f'{i + 1}. {pattern_label} · seed {tile.seed}')
        self.tile_list.setCurrentRow(min(selection, len(c.tiles) - 1))
        self.update_tile_buttons()
        self.add_studio_tile_button.setEnabled(d.shape in ('triangle', 'hexagon') and
                                               (not c.tiles or c.tiles[0].shape == d.shape))
        self.tile_width.setValue(c.width)
        self.tile_height.setValue(c.height)
        self.tile_swap_button.setEnabled(c.width != c.height)
        self.tile_size.setValue(c.tile_size)
        self.select_canvas_preset(self.tile_preset, c.width, c.height)
        self.undo_action.setEnabled(self.history_index > 0)
        self.redo_action.setEnabled(self.history_index < len(self.history) - 1)
        self.loading = False
        dirty = self.document.to_dict() != self.saved_document
        filename = self.document_path.name if self.document_path else 'Untitled'
        self.setWindowTitle(f'{filename}{" *" if dirty else ""} — {APP_NAME}')
        self.update_heading()

    def change_document(self, document, key='', history=True):
        if self.loading or document == self.document:
            return
        old = self.document
        self.document = document
        if history:
            self.history = self.history[:self.history_index + 1]
            now = time.monotonic()
            if key and self.last_edit[0] == key and now - self.last_edit[1] < .6 and self.history_index:
                self.history[-1] = document
            else:
                self.history.append(document)
                self.history = self.history[-100:]
            self.history_index = len(self.history) - 1
            self.last_edit = (key, now)
        self.load_widgets()
        if old.design != document.design or old.composition != document.composition:
            self.invalidate_render()

    def update_design(self, key='', **changes):
        if not self.loading:
            try:
                self.change_document(replace(self.document, design=replace(self.document.design, **changes)), key)
            except ValueError as error:
                self.error(str(error))
                self.load_widgets()

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.last_edit = ('', 0)
            self.change_document(self.history[self.history_index], history=False)

    def redo(self):
        if self.history_index + 1 < len(self.history):
            self.history_index += 1
            self.last_edit = ('', 0)
            self.change_document(self.history[self.history_index], history=False)

    def pattern_changed(self, *_):
        if not self.loading:
            self.update_design(pattern=self.pattern.currentData())

    def planet_type_changed(self, *_):
        if not self.loading:
            self.update_design(planet_type=self.planet_type.currentData())

    def palette_changed(self, *_):
        if not self.loading:
            palette = self.palette.currentData()
            self.update_design(palette=palette, colors=PALETTES[palette][1])

    def reset_pattern(self):
        d = self.document.design
        defaults = MarbleGenerator.MARBLE_STYLES.get(
            d.planet_type if d.pattern == 'planetary' else 'carrara')
        self.update_design(intensity=1.0, vein_intensity=defaults.vein_intensity,
                           vein_scale=defaults.vein_scale, complexity=defaults.complexity,
                           texture_scale=defaults.texture_scale)

    def reset_palette(self):
        d = self.document.design
        self.update_design(colors=PALETTES[d.palette][1])

    def update_palette_buttons(self, *_):
        index = self.palette_list.currentRow()
        count = self.palette_list.count()
        self.color_remove.setEnabled(index >= 0 and count > 2)
        self.color_choose.setEnabled(index >= 0)
        self.color_up.setEnabled(index > 0)
        self.color_down.setEnabled(0 <= index < count - 1)

    def update_tile_buttons(self, *_):
        index = self.tile_list.currentRow()
        count = self.tile_list.count()
        self.tile_remove.setEnabled(index >= 0)
        self.tile_up.setEnabled(index > 0)
        self.tile_down.setEnabled(0 <= index < count - 1)

    def palette_edited(self, *_):
        if not self.loading:
            colors = tuple(self.palette_list.item(i).text() for i in range(self.palette_list.count()))
            self.update_design(colors=colors)

    def choose_color(self):
        index = self.palette_list.currentRow()
        if index < 0:
            return
        color = QColorDialog.getColor(QColor(self.document.design.colors[index]), self, 'Palette color')
        if color.isValid():
            colors = list(self.document.design.colors)
            colors[index] = color.name().upper()
            self.update_design(colors=tuple(colors))

    def add_color(self):
        self.update_design(colors=self.document.design.colors + ('#FFFFFF',))
        self.palette_list.setCurrentRow(self.palette_list.count() - 1)

    def remove_color(self):
        index = self.palette_list.currentRow()
        colors = list(self.document.design.colors)
        if len(colors) <= 2:
            self.statusBar().showMessage('Keep at least two colors in the palette.', 5000)
        elif index >= 0:
            colors.pop(index)
            self.update_design(colors=tuple(colors))

    def move_color(self, offset):
        index = self.palette_list.currentRow()
        colors = list(self.document.design.colors)
        if index >= 0 and 0 <= index + offset < len(colors):
            colors[index], colors[index + offset] = colors[index + offset], colors[index]
            self.update_design(colors=tuple(colors))
            self.palette_list.setCurrentRow(index + offset)

    def shape_changed(self, *_):
        if not self.loading:
            shape = self.shape.currentData()
            changes = {'shape': shape}
            if shape == 'circle':
                changes['height'] = self.document.design.width
            self.update_design(**changes)

    def dimension_changed(self, key, value):
        changes = {key: value}
        if self.document.design.shape == 'circle':
            changes = {'width': value, 'height': value}
        self.update_design('', **changes)

    def size_preset_changed(self, *_):
        if self.loading or not self.size_preset.currentData():
            return
        width, height = self.size_preset.currentData()
        shape = self.document.design.shape
        if width != height and shape == 'circle':
            shape = 'rectangle'
        self.update_design(shape=shape, width=width, height=height)

    def swap_dimensions(self):
        d = self.document.design
        if d.width != d.height:
            self.update_design(width=d.height, height=d.width)

    @staticmethod
    def select_canvas_preset(combo, width, height):
        index = next((i for i in range(1, combo.count()) if combo.itemData(i) == (width, height)), 0)
        combo.setCurrentIndex(index)

    def tile_preset_changed(self, *_):
        if self.loading or not self.tile_preset.currentData():
            return
        width, height = self.tile_preset.currentData()
        composition = replace(self.document.composition, width=width, height=height)
        self.change_document(replace(self.document, composition=composition))

    def swap_tile_dimensions(self):
        c = self.document.composition
        if c.width != c.height:
            self.change_document(replace(self.document, composition=replace(c, width=c.height, height=c.width)))

    def new_variation(self):
        if not self.document.seed_locked:
            self.update_design(seed=secrets.randbelow(2**31))

    def batch_settings_changed(self, *_):
        if self.loading:
            return True
        try:
            text = self.batch_sizes.text().strip()
            sizes = tuple(tuple(int(v.strip()) for v in token.lower().replace('×', 'x').split('x'))
                          for token in text.split(',')) if text else ()
            settings = BatchSettings(self.batch_count.value(), self.vary_palette.isChecked(), self.vary_texture.isChecked(),
                                     SCHEMES[self.scheme.currentIndex()], sizes,
                                     {name: tuple(w.value() for w in widgets) for name, widgets in self.range_controls.items()})
            self.change_document(replace(self.document, batch=settings))
            return True
        except ValueError as error:
            self.error(f'Check batch settings: {error}')
            self.load_widgets()
            return False

    def composition_settings_changed(self, *_):
        if not self.loading:
            composition = replace(self.document.composition, width=self.tile_width.value(),
                                  height=self.tile_height.value(), tile_size=self.tile_size.value())
            self.change_document(replace(self.document, composition=composition))

    def add_tiles(self, tiles):
        try:
            composition = replace(self.document.composition, tiles=self.document.composition.tiles + tuple(tiles))
            self.change_document(replace(self.document, composition=composition))
            self.tabs.setCurrentIndex(2)
        except ValueError as error:
            self.error(str(error))

    def add_studio_tile(self):
        self.add_tiles([self.document.design])

    def add_tiles_from_batch(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open saved batch manifest', '', 'Batch manifest (*.json)')
        if not path:
            return
        try:
            manifest = json.loads(Path(path).read_text(encoding='utf-8'))
            if manifest.get('kind') != 'marble-studio-batch' or not isinstance(manifest.get('entries'), list):
                raise ValueError('This file is not a compatible batch manifest.')
            entries = [(entry, Design.from_dict(entry['recipe'])) for entry in manifest['entries']
                       if entry.get('status') == 'complete']
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.error(f'Could not read complete batch recipes: {error}')
            return
        if not entries:
            self.error('This manifest has no completed recipes.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Choose tiles from batch')
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Select completed triangle or hexagon recipes of one shape.'))
        choices = QListWidget()
        choices.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for entry, recipe in entries:
            item = QListWidgetItem(f'{Path(entry.get("file", "image")).name} · {recipe.shape} · seed {recipe.seed}')
            if recipe.shape not in ('triangle', 'hexagon'):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip('Geometric tiling currently supports triangles and hexagons only.')
            choices.addItem(item)
        layout.addWidget(choices)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = [entries[choices.row(item)][1] for item in choices.selectedItems()]
        if not selected:
            self.error('Select at least one completed triangle or hexagon recipe.')
        elif len({item.shape for item in selected} | {item.shape for item in self.document.composition.tiles}) > 1:
            self.error('A tiling composition can contain only one shape. Choose triangles or hexagons, not both.')
        else:
            self.add_tiles(selected)

    def remove_tile(self):
        index = self.tile_list.currentRow()
        if index >= 0:
            tiles = list(self.document.composition.tiles)
            tiles.pop(index)
            self.change_document(replace(self.document, composition=replace(self.document.composition, tiles=tuple(tiles))))

    def move_tile(self, offset):
        index = self.tile_list.currentRow()
        tiles = list(self.document.composition.tiles)
        if index >= 0 and 0 <= index + offset < len(tiles):
            tiles[index], tiles[index + offset] = tiles[index + offset], tiles[index]
            self.change_document(replace(self.document, composition=replace(self.document.composition, tiles=tuple(tiles))))
            self.tile_list.setCurrentRow(index + offset)

    def current_request(self):
        if self.tabs.currentIndex() == 2:
            if not self.document.composition.tiles:
                return None
            return {'kind': 'tiling', 'recipe': asdict(self.document.composition)}
        return {'kind': 'design', 'recipe': asdict(self.document.design)}

    @staticmethod
    def request_key(request):
        return json.dumps({'kind': request['kind'], 'recipe': request['recipe']}, sort_keys=True)

    def update_heading(self):
        if self.tabs.currentIndex() == 2:
            c = self.document.composition
            self.preview_title.setText(f'Tiled wallpaper · {c.width} × {c.height}')
        else:
            d = self.document.design
            pattern_label = (f'Planetary · {PLANET_TYPES[d.planet_type]}'
                             if d.pattern == 'planetary' else PATTERNS[d.pattern])
            self.preview_title.setText(f'{pattern_label} · {d.shape}')

    def workspace_changed(self, *_):
        self.update_heading()
        self.invalidate_render()

    def invalidate_render(self):
        self.revision += 1
        self.latest_render = None
        self.final_cache.clear()
        self.jobs.cancel_interactive()
        self.preview.clear_image()
        self.preview_state.setText('Rendering full-resolution image…')
        self.retry_button.setVisible(False)
        self.debounce.start()

    def request_render(self):
        if self.batch_run or self.export_pending:
            return
        request = self.current_request()
        if request is None:
            self.preview.clear_image()
            self.preview_state.setText('Add a triangle or hexagon design to preview a wallpaper.')
            return
        request.update(interactive=True, revision=self.revision)
        self.latest_render = self.jobs.submit(request)

    def render_final(self, *_ , export_target=None):
        if self.batch_run or self.export_pending:
            return
        request = self.current_request()
        if request is None:
            self.error('Add at least one triangle or hexagon to the composition first.')
            return
        self.debounce.stop()
        # Promote an already-running exact render instead of starting it again
        # when Export is requested during automatic rendering.
        if self.jobs.active:
            active_request = self.jobs.active[1]
            if (active_request.get('interactive') and active_request['revision'] == self.revision
                    and self.request_key(active_request) == self.request_key(request)):
                active_request.pop('interactive')
                active_request['export_target'] = export_target
                self.export_pending = True
                self.busy_changed(True)
                return
        self.jobs.cancel_interactive()
        request.update(revision=self.revision, export_target=export_target)
        self.export_pending = True
        self.jobs.submit(request)

    def export_png(self):
        if self.batch_run or self.export_pending:
            return
        request = self.current_request()
        if request is None:
            self.error('Add a tile to the composition before exporting.')
            return
        target, _ = QFileDialog.getSaveFileName(self, 'Export PNG (existing files receive a numbered name)',
                                               'marble.png', 'PNG image (*.png)',
                                               options=QFileDialog.Option.DontConfirmOverwrite)
        if not target:
            return
        target = str(Path(target).with_suffix('.png'))
        key = self.request_key(request)
        if key in self.final_cache:
            self.export_pending = True
            self.jobs.submit({'kind': 'commit', 'source': self.final_cache[key], 'target': target})
        else:
            self.render_final(export_target=target)

    def on_result(self, job_id, request, result):
        if request['kind'] == 'commit':
            if request.get('batch_index') is not None:
                self.batch_committed(request, result)
            else:
                self.export_pending = False
                self.statusBar().showMessage(f'Saved {result}', 12000)
                current = self.current_request()
                if current and self.request_key(current) not in self.final_cache:
                    self.debounce.start()
                if self.close_after_save:
                    self.close_after_save = False
                    self.close()
            return
        if request.get('batch_index') is not None:
            if self.batch_run and not self.batch_run['cancelled']:
                self.batch_run['rendered'] = result
                index = request['batch_index']
                self.jobs.submit({'kind': 'commit', 'source': result['path'],
                                  'target': self.batch_run['entries'][index]['file'], 'batch_index': index})
            return
        if request.get('interactive'):
            if job_id != self.latest_render or request['revision'] != self.revision:
                return
        if request.get('export_target') and request['revision'] != self.revision:
            self.export_pending = False
            self.render_final(export_target=request['export_target'])
            return
        if request['revision'] == self.revision:
            self.final_cache[self.request_key(request)] = result['path']
            self.preview.show_image(result['path'])
            self.preview_state.setText('Final image · exact export pixels')
            self.retry_button.setVisible(False)
            self.statusBar().showMessage('Image ready to export', 7000)
        if request.get('export_target'):
            self.jobs.submit({'kind': 'commit', 'source': result['path'], 'target': request['export_target']})
        elif not request.get('interactive'):
            self.export_pending = False
            if request['revision'] != self.revision:
                self.debounce.start()

    def start_batch(self):
        if self.batch_run or self.export_pending or not self.batch_settings_changed():
            return
        try:
            recipes = batch_recipes(self.document.design, self.document.batch)
        except ValueError as error:
            self.error(str(error))
            return
        folder = QFileDialog.getExistingDirectory(self, 'Save batch PNGs and recipe manifest')
        if not folder:
            return
        self.debounce.stop()
        self.jobs.cancel_interactive()
        token = uuid4().hex[:8]
        entries = [{'recipe': asdict(recipe), 'file': str(Path(folder) / f'marble_{token}_{i + 1:04d}.png'), 'status': 'pending'}
                   for i, recipe in enumerate(recipes)]
        self.batch_run = {'entries': entries, 'index': 0, 'cancelled': False, 'manifest': None,
                          'settings': asdict(self.document.batch), 'base_design': asdict(self.document.design)}
        try:
            self.batch_run['manifest'] = save_json(Path(folder) / f'batch_{token}.json', self.batch_manifest())
        except OSError as error:
            self.batch_run = None
            self.error(str(error))
            return
        self.batch_summary.setText(f'Generating {len(entries)} images… Manifest: {self.batch_run["manifest"]}')
        self.start_next_batch_item()

    def batch_manifest(self):
        return {'schema_version': 1, 'kind': 'marble-studio-batch', 'settings': self.batch_run['settings'],
                'base_design': self.batch_run['base_design'], 'entries': self.batch_run['entries']}

    def start_next_batch_item(self):
        run = self.batch_run
        if run['cancelled'] or run['index'] >= len(run['entries']):
            self.finish_batch()
            return
        index = run['index']
        self.jobs.submit({'kind': 'design', 'recipe': run['entries'][index]['recipe'], 'batch_index': index})

    def batch_committed(self, request, path):
        if not self.batch_run:
            return
        run = self.batch_run
        index = request['batch_index']
        entry = run['entries'][index]
        entry.update(file=path, status='complete')
        run['index'] += 1
        self.batch_summary.setText(f'{run["index"]} of {len(run["entries"])} images saved. Manifest: {run["manifest"]}')
        try:
            save_json(run['manifest'], self.batch_manifest(), replace_existing=True)
        except OSError as error:
            self.error(f'Image saved, but the manifest could not be updated: {error}')
            run['cancelled'] = True
        if self.close_after_save:
            run['cancelled'] = True
        self.start_next_batch_item()
        if self.close_after_save:
            self.close_after_save = False
            self.close()

    def finish_batch(self):
        run = self.batch_run
        if run:
            if run['cancelled']:
                for entry in run['entries']:
                    if entry['status'] == 'pending':
                        entry['status'] = 'cancelled'
                try:
                    save_json(run['manifest'], self.batch_manifest(), replace_existing=True)
                except OSError as error:
                    self.error(f'Could not update the batch manifest: {error}')
            self.statusBar().showMessage(f'Batch {"cancelled" if run["cancelled"] else "complete"} · {run["index"]} images saved', 12000)
            self.batch_summary.setText(f'Batch {"cancelled" if run["cancelled"] else "complete"}: '
                                       f'{run["index"]} images saved. Manifest: {run["manifest"]}')
        self.batch_run = None
        self.debounce.start()

    def show_progress(self, message):
        if self.batch_run:
            message = f'Image {self.batch_run["index"] + 1} of {len(self.batch_run["entries"])} · {message}'
        self.statusBar().showMessage(message)

    def busy_changed(self, busy):
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if self.batch_run:
            self.progress.setRange(0, len(self.batch_run['entries']))
            self.progress.setValue(self.batch_run['index'])
        else:
            self.progress.setRange(0, 0)
        available = not self.batch_run and not self.export_pending
        self.export_button.setEnabled(available)
        self.batch_button.setEnabled(not self.batch_run and not self.export_pending)

    def cancel_jobs(self):
        self.debounce.stop()
        self.latest_render = None
        if self.batch_run:
            self.batch_run['cancelled'] = True
        if self.jobs.cancel():
            if self.batch_run:
                self.finish_batch()
            self.export_pending = False
            self.preview_state.setText('Render cancelled. Retry when ready.')
            self.retry_button.setVisible(True)
            self.statusBar().showMessage('Cancelled. Completed files are preserved.', 7000)
            self.busy_changed(False)

    def retry_render(self):
        request = self.failed_request
        self.failed_request = None
        self.retry_button.setVisible(False)
        if request and (request.get('export_target') or request.get('kind') == 'commit'):
            self.render_final(export_target=request.get('export_target') or request['target'])
        elif request and request.get('batch_index') is not None:
            self.start_batch()
        else:
            self.request_render()

    def on_error(self, job_id, request, message):
        if request.get('interactive') and request.get('revision') != self.revision:
            return
        self.export_pending = False
        self.failed_request = request
        retry_label = ('Retry batch…' if request.get('batch_index') is not None else
                       'Retry export' if request.get('export_target') or request.get('kind') == 'commit' else
                       'Retry render')
        self.retry_button.setText(retry_label)
        self.retry_button.setAccessibleName(retry_label)
        self.retry_button.setToolTip(retry_label)
        if self.batch_run:
            self.batch_run['cancelled'] = True
            self.finish_batch()
        self.preview_state.setText('Rendering failed. Check the error and retry.')
        self.retry_button.setVisible(True)
        self.error(message)
        if self.close_after_save:
            self.close_after_save = False
            self.close()

    def error(self, message):
        QMessageBox.warning(self, APP_NAME, message)

    def save_document(self, *_ , save_as=False):
        path = self.document_path
        if save_as or not path:
            selected, _ = QFileDialog.getSaveFileName(self, f'Save {APP_NAME} document',
                                                     str(path or 'design.marble.json'), f'{APP_NAME} document (*.json)')
            if not selected:
                return False
            path = Path(selected)
            if path.suffix.lower() != '.json':
                path = path.with_suffix('.json')
        try:
            save_json(path, self.document.to_dict(), replace_existing=True)
            self.document_path = path
            self.saved_document = self.document.to_dict()
            self.load_widgets()
            self.statusBar().showMessage(f'Saved {path}', 6000)
            return True
        except OSError as error:
            self.error(str(error))
            return False

    def confirm_unsaved(self):
        if self.document.to_dict() == self.saved_document:
            return True
        choice = QMessageBox.question(self, 'Save your design?', 'This document has unsaved changes.',
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Save:
            return self.save_document()
        return choice == QMessageBox.StandardButton.Discard

    def open_document(self):
        if not self.confirm_unsaved():
            return
        path, _ = QFileDialog.getOpenFileName(self, f'Open {APP_NAME} document', '', f'{APP_NAME} document (*.json)')
        if not path:
            return
        try:
            document = Document.load(path)
        except (OSError, ValueError) as error:
            self.error(str(error))
            return
        self.change_document(document)
        self.document_path = Path(path)
        self.saved_document = document.to_dict()
        self.history, self.history_index = [document], 0
        self.load_widgets()

    def closeEvent(self, event):
        if self.jobs.active and self.jobs.active[1]['kind'] == 'commit':
            self.close_after_save = True
            self.statusBar().showMessage('Finishing the current file save before closing…')
            event.ignore()
            return
        if not self.confirm_unsaved():
            event.ignore()
            return
        if self.batch_run:
            self.batch_run['cancelled'] = True
            self.finish_batch()
        self.debounce.stop()
        self.jobs.shutdown()
        event.accept()
