"""Small, accessible Qt controls and an artwork-first preview."""
from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QSlider,
    QDoubleSpinBox, QSpinBox, QComboBox, QGraphicsView, QGraphicsScene, QFrame,
)


def scroll_settings_panel(control, event):
    parent = control.parentWidget()
    while parent and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    if parent:
        viewport = parent.viewport()
        scrollbar = parent.verticalScrollBar()
        previous = scrollbar.value()
        position = control.mapTo(viewport, event.position().toPoint())
        forwarded = QWheelEvent(QPointF(position), event.globalPosition(), event.pixelDelta(),
                                event.angleDelta(), event.buttons(), event.modifiers(),
                                event.phase(), event.inverted())
        QApplication.sendEvent(viewport, forwarded)
        if scrollbar.value() == previous and event.pixelDelta().y():
            scrollbar.setValue(previous - event.pixelDelta().y())
        if forwarded.isAccepted():
            event.accept()
            return
        if scrollbar.value() != previous:
            event.accept()
            return
    event.ignore()


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        scroll_settings_panel(self, event)


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        scroll_settings_panel(self, event)


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        scroll_settings_panel(self, event)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        if self.view().isVisible():
            bar = self.view().verticalScrollBar()
            delta = event.pixelDelta().y() or event.angleDelta().y() / 4
            bar.setValue(bar.value() - round(delta))
            event.accept()
        else:
            scroll_settings_panel(self, event)


class Section(QWidget):
    def __init__(self, title, expanded=True):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        self.toggle = QToolButton(text=title)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setStyleSheet('QToolButton { font-weight: 600; padding: 6px 0; border: none; }')
        self.body = QWidget()
        self.content = QVBoxLayout(self.body)
        self.content.setContentsMargins(2, 4, 2, 0)
        self.content.setSpacing(10)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self.expand)
        self.expand(expanded)

    def expand(self, checked):
        self.body.setVisible(checked)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)


class NumberControl(QWidget):
    changed = Signal(object)

    def __init__(self, low, high, *, decimals=2, step=.01, name=''):
        super().__init__()
        self.low, self.high, self.decimals = low, high, decimals
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((high - low) / step))
        self.step = step
        self.spin = NoWheelSpinBox() if decimals == 0 else NoWheelDoubleSpinBox()
        if decimals:
            self.spin.setDecimals(decimals)
        self.spin.setRange(low, high)
        self.spin.setSingleStep(step)
        self.spin.setKeyboardTracking(False)
        self.spin.setMinimumWidth(80)
        self.slider.setAccessibleName(name)
        self.spin.setAccessibleName(name + ' value')
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self.slider.valueChanged.connect(lambda value: self.spin.setValue(round(low + value * step, decimals)))
        self.spin.valueChanged.connect(self._spin_changed)

    def _spin_changed(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self.low) / self.step))
        self.slider.blockSignals(False)
        self.changed.emit(value)

    def setValue(self, value):
        self.spin.blockSignals(True)
        self.spin.setValue(value)
        self.spin.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self.low) / self.step))
        self.slider.blockSignals(False)

    def value(self):
        return self.spin.value()


class Preview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.art = None
        self.fit_mode = True
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAccessibleName('Marble artwork preview. Use zoom buttons or Control plus mouse wheel to zoom.')
        self.setMinimumSize(240, 240)

    def drawBackground(self, painter, rect):
        # Paint in viewport coordinates so checker squares do not change on zoom.
        painter.save()
        painter.resetTransform()
        dark = self.palette().window().color().lightness() < 128
        a, b = ('#34383E', '#41464D') if dark else ('#E4E8ED', '#F4F6F8')
        painter.fillRect(self.viewport().rect(), QColor(a))
        for y in range(0, self.viewport().height(), 16):
            for x in range(0, self.viewport().width(), 16):
                if (x // 16 + y // 16) % 2:
                    painter.fillRect(x, y, 16, 16, QColor(b))
        painter.restore()

    def show_image(self, path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError('Could not load the rendered preview')
        self.scene().clear()
        self.art = self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        if self.fit_mode:
            self.fit()

    def clear_image(self):
        self.scene().clear()
        self.art = None

    def fit(self):
        self.fit_mode = True
        if self.art:
            self.fitInView(self.art, Qt.AspectRatioMode.KeepAspectRatio)

    def actual(self):
        self.fit_mode = False
        self.resetTransform()
        # One image pixel per physical display pixel on Retina/high-DPI screens.
        ratio = 1 / self.devicePixelRatioF()
        self.scale(ratio, ratio)

    def zoom(self, factor):
        self.fit_mode = False
        scale = self.transform().m11() * factor
        if .01 <= scale <= 32:
            self.scale(factor, factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode:
            QTimer.singleShot(0, self._fit_if_requested)

    def _fit_if_requested(self):
        if self.fit_mode:
            self.fit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
        else:
            super().wheelEvent(event)
