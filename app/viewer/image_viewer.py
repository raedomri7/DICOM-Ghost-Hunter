"""DICOM image viewer widget using matplotlib embedded in PyQt5.

Provides:
- Axial image display with imshow.
- Window / Level (brightness / contrast) adjustment.
- Slice navigation (previous / next / index slider).
- Pan / zoom via the matplotlib navigation toolbar.
- Display of image metadata and current slice position.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.backends.backend_qt5agg import (
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.viewer.slice_navigation import SliceNavigator
from app.viewer.window_level import WindowLevel


class DicomImageViewer(QWidget):
    """A single-series DICOM image viewer embedded in PyQt5."""

    slice_changed = pyqtSignal(int, int)  # current_index, total_count
    window_level_changed = pyqtSignal(float, float)  # window, level

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.navigator: SliceNavigator | None = None
        self.window_level: WindowLevel | None = None
        self._current_array: np.ndarray | None = None
        self._image_artist: Any = None

        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- Matplotlib canvas + toolbar ---
        self.figure = Figure(figsize=(5, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title("No image loaded")
        self.axes.axis("off")
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

        # --- Slice navigation controls ---
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self._on_previous)
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self._on_next)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.slice_label = QLabel("Slice 0/0")
        self.slice_label.setAlignment(Qt.AlignCenter)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.slice_label)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.slider)
        layout.addLayout(nav_layout)

        # --- Window / Level controls ---
        wl_layout = QHBoxLayout()

        self.spin_window = QDoubleSpinBox()
        self.spin_window.setRange(-1e6, 1e6)
        self.spin_window.setDecimals(2)
        self.spin_window.setSuffix(" WW")
        self.spin_window.valueChanged.connect(self._on_window_changed)

        self.spin_level = QDoubleSpinBox()
        self.spin_level.setRange(-1e6, 1e6)
        self.spin_level.setDecimals(2)
        self.spin_level.setSuffix(" WL")
        self.spin_level.valueChanged.connect(self._on_level_changed)

        self.btn_auto = QPushButton("Auto W/L")
        self.btn_auto.clicked.connect(self._on_auto_window_level)

        self.info_label = QLabel("No data")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #9aa5b1; font-size: 11px;")

        wl_layout.addWidget(QLabel("Window:"))
        wl_layout.addWidget(self.spin_window)
        wl_layout.addWidget(QLabel("Level:"))
        wl_layout.addWidget(self.spin_level)
        wl_layout.addWidget(self.btn_auto)
        wl_layout.addStretch()
        layout.addLayout(wl_layout)
        layout.addWidget(self.info_label)

        self._set_enabled(False)

    # ------------------------------------------------------------------ #
    def _set_enabled(self, enabled: bool) -> None:
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.spin_window.setEnabled(enabled)
        self.spin_level.setEnabled(enabled)
        self.btn_auto.setEnabled(enabled)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load_series(self, instances: list[Any]) -> None:
        """Load a list of DICOM instances as a viewable series."""
        self.clear()
        if not instances:
            return

        self.navigator = SliceNavigator(instances)
        self.window_level = WindowLevel.from_data(self.navigator.get_current_array())
        self._sync_spinboxes()
        self._set_enabled(True)
        self._refresh_display()

    @property
    def current_array(self) -> np.ndarray | None:
        """The currently displayed slice array, or None if no series is loaded."""
        return self._current_array

    def clear(self) -> None:
        self.navigator = None
        self.window_level = None
        self._current_array = None
        self._image_artist = None
        self.axes.clear()
        self.axes.set_title("No image loaded")
        self.axes.axis("off")
        self.canvas.draw_idle()
        self.slice_label.setText("Slice 0/0")
        self.info_label.setText("No data")
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self._set_enabled(False)

    # ------------------------------------------------------------------ #
    # Display
    # ------------------------------------------------------------------ #
    def _refresh_display(self) -> None:
        if self.navigator is None or self.window_level is None:
            return

        array = self.navigator.get_current_array()
        if array is None:
            self.axes.clear()
            self.axes.set_title("Unable to decode pixels")
            self.axes.axis("off")
            self.canvas.draw_idle()
            return

        self._current_array = array
        vmin, vmax = self.window_level.get_vmin_vmax()

        if self._image_artist is None:
            self._image_artist = self.axes.imshow(
                array, cmap="gray", vmin=vmin, vmax=vmax, origin="upper"
            )
            self.axes.set_title("DICOM Image")
            self.axes.axis("off")
        else:
            self._image_artist.set_data(array)
            self._image_artist.set_clim(vmin, vmax)

        # Index slider
        total = self.navigator.count
        self.slider.setMaximum(max(total - 1, 0))
        self.slider.setValue(self.navigator.index)

        # Labels
        self.slice_label.setText(self.navigator.get_slice_label())
        self.info_label.setText(
            f"Shape: {array.shape} | dtype: {array.dtype} | "
            f"min: {float(array.min()):.1f} | max: {float(array.max()):.1f}"
        )

        self.canvas.draw_idle()
        self.slice_changed.emit(self.navigator.index, total)

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #
    def _on_previous(self) -> None:
        if self.navigator is None:
            return
        self.navigator.previous_slice()
        self._refresh_display()

    def _on_next(self) -> None:
        if self.navigator is None:
            return
        self.navigator.next_slice()
        self._refresh_display()

    def _on_slider_changed(self, value: int) -> None:
        if self.navigator is None:
            return
        self.navigator.set_index(value)
        self._refresh_display()

    def _on_window_changed(self, value: float) -> None:
        if self.window_level is None:
            return
        self.window_level.set_window_width(value)
        self._refresh_display()
        self.window_level_changed.emit(value, self.window_level.get_window_level())

    def _on_level_changed(self, value: float) -> None:
        if self.window_level is None:
            return
        self.window_level.set_window_level(value)
        self._refresh_display()
        self.window_level_changed.emit(self.window_level.get_window_width(), value)

    def _on_auto_window_level(self) -> None:
        if self.navigator is None or self._current_array is None:
            return
        self.window_level = WindowLevel.from_data(self._current_array)
        self._sync_spinboxes()
        self._refresh_display()

    def _sync_spinboxes(self) -> None:
        if self.window_level is None:
            return
        self.spin_window.setValue(self.window_level.get_window_width())
        self.spin_level.setValue(self.window_level.get_window_level())
