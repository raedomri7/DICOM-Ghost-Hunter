"""Window / Level (brightness / contrast) logic for DICOM display."""

from __future__ import annotations

import numpy as np


class WindowLevel:
    """Computes display window (vmin/vmax) from window width / window level.

    Window Level (WL) = center of the display window.
    Window Width (WW) = width of the display window.
    vmin = WL - WW / 2
    vmax = WL + WW / 2
    """

    def __init__(
        self,
        window_width: float | None = None,
        window_level: float | None = None,
        data_min: float | None = None,
        data_max: float | None = None,
    ) -> None:
        self.window_width = window_width
        self.window_level = window_level
        self.data_min = data_min
        self.data_max = data_max

    @classmethod
    def from_data(cls, array: np.ndarray) -> WindowLevel:
        """Create a WindowLevel using the full data range (auto window/level)."""
        data_min = float(np.min(array))
        data_max = float(np.max(array))
        window_width = data_max - data_min if data_max > data_min else 1.0
        window_level = (data_min + data_max) / 2.0
        return cls(
            window_width=window_width,
            window_level=window_level,
            data_min=data_min,
            data_max=data_max,
        )

    def set_window_width(self, width: float) -> None:
        self.window_width = float(width)

    def set_window_level(self, level: float) -> None:
        self.window_level = float(level)

    def get_vmin_vmax(self) -> tuple[float, float]:
        """Return (vmin, vmax) for matplotlib imshow clim."""
        if self.window_width is None or self.window_level is None:
            raise ValueError("Window width and level must be set.")
        ww = self.window_width
        wl = self.window_level
        if ww <= 0:
            ww = 1.0
        vmin = wl - ww / 2.0
        vmax = wl + ww / 2.0
        return vmin, vmax

    def get_window_width(self) -> float:
        return self.window_width if self.window_width is not None else 0.0

    def get_window_level(self) -> float:
        return self.window_level if self.window_level is not None else 0.0
