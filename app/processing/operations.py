"""Image Processing Laboratory — core operation framework.

Every operation:
- Accepts a NumPy array (single 2D slice).
- Returns a derived NumPy array (never modifies the input).
- Exposes adjustable parameters as a plain dict.
- Is traceable (name, parameters, timestamp) for reporting.

Original DICOM data and metadata are preserved; processed results are stored
as separate derived arrays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingOperation:
    """Describes a single image-processing operation."""

    name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    applied_at: str | None = None
    input_shape: tuple[int, ...] | None = None
    output_shape: tuple[int, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "applied_at": self.applied_at,
            "input_shape": self.input_shape,
            "output_shape": self.output_shape,
        }


class ImageProcessor:
    """Applies image-processing operations to 2D image arrays.

    All methods return new arrays; inputs are never mutated.
    """

    def __init__(self) -> None:
        self.history: list[ProcessingOperation] = []

    # ------------------------------------------------------------------ #
    # Registry of available operations
    # ------------------------------------------------------------------ #
    def available_operations(self) -> list[str]:
        """Return the list of operation names supported by this processor."""
        return [
            "normalize_minmax",
            "normalize_zscore",
            "normalize_percentile",
            "contrast_adjust",
            "brightness_adjust",
            "gamma_correction",
            "invert",
            "clip",
            "gaussian_filter",
            "median_filter",
            "bilateral_filter",
            "histogram_equalization",
            "clahe",
            "unsharp_masking",
            "sobel",
            "prewitt",
            "laplacian",
            "canny",
            "gradient_magnitude",
            "erosion",
            "dilation",
            "opening",
            "closing",
            "morphological_gradient",
            "fft_spectrum",
            "lowpass_filter",
            "highpass_filter",
        ]

    # ------------------------------------------------------------------ #
    # Preprocessing / normalization
    # ------------------------------------------------------------------ #
    def normalize_minmax(self, array: np.ndarray) -> np.ndarray:
        """Scale array to [0, 1] using min-max normalization."""
        arr = np.asarray(array, dtype=np.float64)
        data_min = float(arr.min())
        data_max = float(arr.max())
        if data_max > data_min:
            return (arr - data_min) / (data_max - data_min)
        return np.zeros_like(arr, dtype=np.float64)

    def normalize_zscore(self, array: np.ndarray) -> np.ndarray:
        """Zero-mean, unit-variance normalization."""
        arr = np.asarray(array, dtype=np.float64)
        mean = float(arr.mean())
        std = float(arr.std())
        if std > 0:
            return (arr - mean) / std
        return arr - mean

    def normalize_percentile(
        self, array: np.ndarray, low: float = 1.0, high: float = 99.0
    ) -> np.ndarray:
        """Clip to percentile range then scale to [0, 1]."""
        arr = np.asarray(array, dtype=np.float64)
        p_low = float(np.percentile(arr, low))
        p_high = float(np.percentile(arr, high))
        if p_high > p_low:
            clipped = np.clip(arr, p_low, p_high)
            return (clipped - p_low) / (p_high - p_low)
        return np.zeros_like(arr, dtype=np.float64)

    # ------------------------------------------------------------------ #
    # Contrast / brightness
    # ------------------------------------------------------------------ #
    def contrast_adjust(self, array: np.ndarray, factor: float = 1.0) -> np.ndarray:
        """Adjust contrast around the mean."""
        arr = np.asarray(array, dtype=np.float64)
        mean = float(arr.mean())
        return mean + factor * (arr - mean)

    def brightness_adjust(self, array: np.ndarray, offset: float = 0.0) -> np.ndarray:
        """Add a constant offset to all pixels."""
        arr = np.asarray(array, dtype=np.float64)
        return arr + float(offset)

    def gamma_correction(self, array: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        """Apply gamma correction after normalizing to [0, 1]."""
        arr = self.normalize_minmax(array)
        if gamma <= 0:
            gamma = 1.0
        return np.power(np.clip(arr, 0.0, 1.0), 1.0 / gamma)

    def invert(self, array: np.ndarray) -> np.ndarray:
        """Invert intensities after normalizing to [0, 1]."""
        return 1.0 - self.normalize_minmax(array)

    def clip(self, array: np.ndarray, low: float, high: float) -> np.ndarray:
        """Clip intensities to [low, high] then normalize to [0, 1]."""
        arr = np.asarray(array, dtype=np.float64)
        return self.normalize_minmax(np.clip(arr, low, high))

    # ------------------------------------------------------------------ #
    # Noise reduction / filtering
    # ------------------------------------------------------------------ #
    def gaussian_filter(self, array: np.ndarray, sigma: float = 1.0) -> np.ndarray:
        """Gaussian smoothing using SciPy."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        return ndimage.gaussian_filter(arr, sigma=float(sigma))

    def median_filter(self, array: np.ndarray, size: int = 3) -> np.ndarray:
        """Median filtering for salt-and-pepper noise reduction."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        return ndimage.median_filter(arr, size=int(size))

    def bilateral_filter(self, array: np.ndarray, sigma_color: float = 10.0, sigma_spatial: float = 5.0) -> np.ndarray:
        """Bilateral filtering (edge-preserving smoothing) via OpenCV."""
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        # Normalize to [0, 255] uint8 for OpenCV bilateralFilter
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        filtered = cv2.bilateralFilter(
            uint8, d=0, sigmaColor=float(sigma_color), sigmaSpace=float(sigma_spatial)
        )
        return filtered.astype(np.float64) / 255.0

    # ------------------------------------------------------------------ #
    # Enhancement
    # ------------------------------------------------------------------ #
    def histogram_equalization(self, array: np.ndarray) -> np.ndarray:
        """Global histogram equalization."""
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        eq = cv2.equalizeHist(uint8)
        return eq.astype(np.float64) / 255.0

    def clahe(self, array: np.ndarray, clip_limit: float = 2.0, tile_grid: int = 8) -> np.ndarray:
        """Contrast Limited Adaptive Histogram Equalization."""
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        clahe_obj = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(int(tile_grid), int(tile_grid)))
        eq = clahe_obj.apply(uint8)
        return eq.astype(np.float64) / 255.0

    def unsharp_masking(self, array: np.ndarray, sigma: float = 1.0, strength: float = 1.0) -> np.ndarray:
        """Sharpen by subtracting a blurred version."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        blurred = ndimage.gaussian_filter(arr, sigma=float(sigma))
        return arr + float(strength) * (arr - blurred)

    # ------------------------------------------------------------------ #
    # Edge detection
    # ------------------------------------------------------------------ #
    def sobel(self, array: np.ndarray) -> np.ndarray:
        """Sobel edge magnitude."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        dx = ndimage.sobel(arr, axis=0)
        dy = ndimage.sobel(arr, axis=1)
        return np.hypot(dx, dy)

    def prewitt(self, array: np.ndarray) -> np.ndarray:
        """Prewitt edge magnitude."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        dx = ndimage.prewitt(arr, axis=0)
        dy = ndimage.prewitt(arr, axis=1)
        return np.hypot(dx, dy)

    def laplacian(self, array: np.ndarray) -> np.ndarray:
        """Laplacian edge detection."""
        from scipy import ndimage

        arr = np.asarray(array, dtype=np.float64)
        return ndimage.laplace(arr)

    def canny(self, array: np.ndarray, low_threshold: float = 50.0, high_threshold: float = 150.0) -> np.ndarray:
        """Canny edge detection via OpenCV."""
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        edges = cv2.Canny(uint8, int(low_threshold), int(high_threshold))
        return edges.astype(np.float64) / 255.0

    def gradient_magnitude(self, array: np.ndarray) -> np.ndarray:
        """Gradient magnitude using central differences."""
        arr = np.asarray(array, dtype=np.float64)
        dx = np.gradient(arr, axis=0)
        dy = np.gradient(arr, axis=1)
        return np.hypot(dx, dy)

    # ------------------------------------------------------------------ #
    # Morphology
    # ------------------------------------------------------------------ #
    def erosion(self, array: np.ndarray, iterations: int = 1) -> np.ndarray:
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        eroded = cv2.erode(uint8, None, iterations=int(iterations))
        return eroded.astype(np.float64) / 255.0

    def dilation(self, array: np.ndarray, iterations: int = 1) -> np.ndarray:
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        dilated = cv2.dilate(uint8, None, iterations=int(iterations))
        return dilated.astype(np.float64) / 255.0

    def opening(self, array: np.ndarray, iterations: int = 1) -> np.ndarray:
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        opened = cv2.morphologyEx(uint8, cv2.MORPH_OPEN, None, iterations=int(iterations))
        return opened.astype(np.float64) / 255.0

    def closing(self, array: np.ndarray, iterations: int = 1) -> np.ndarray:
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        closed = cv2.morphologyEx(uint8, cv2.MORPH_CLOSE, None, iterations=int(iterations))
        return closed.astype(np.float64) / 255.0

    def morphological_gradient(self, array: np.ndarray, iterations: int = 1) -> np.ndarray:
        import cv2

        arr = np.asarray(array, dtype=np.float64)
        norm = self.normalize_minmax(arr)
        uint8 = (norm * 255).astype(np.uint8)
        grad = cv2.morphologyEx(uint8, cv2.MORPH_GRADIENT, None, iterations=int(iterations))
        return grad.astype(np.float64) / 255.0

    # ------------------------------------------------------------------ #
    # Frequency domain
    # ------------------------------------------------------------------ #
    def fft_spectrum(self, array: np.ndarray) -> np.ndarray:
        """Compute the log magnitude of the 2D FFT spectrum."""
        arr = np.asarray(array, dtype=np.float64)
        f = np.fft.fft2(arr)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        # Log scale for visualization
        return np.log1p(magnitude)

    def lowpass_filter(self, array: np.ndarray, cutoff: float = 30.0) -> np.ndarray:
        """Ideal low-pass filter in the frequency domain."""
        arr = np.asarray(array, dtype=np.float64)
        rows, cols = arr.shape
        crow, ccol = rows // 2, cols // 2
        f = np.fft.fft2(arr)
        fshift = np.fft.fftshift(f)
        mask = np.zeros((rows, cols), np.float64)
        y, x = np.ogrid[:rows, :cols]
        dist = np.sqrt((x - ccol) ** 2 + (y - crow) ** 2)
        mask[dist <= cutoff] = 1.0
        fshift = fshift * mask
        f_ishift = np.fft.ifftshift(fshift)
        return np.real(np.fft.ifft2(f_ishift))

    def highpass_filter(self, array: np.ndarray, cutoff: float = 30.0) -> np.ndarray:
        """Ideal high-pass filter in the frequency domain."""
        arr = np.asarray(array, dtype=np.float64)
        low = self.lowpass_filter(arr, cutoff=cutoff)
        return arr - low

    # ------------------------------------------------------------------ #
    # Pipeline execution
    # ------------------------------------------------------------------ #
    def apply(self, array: np.ndarray, operation_name: str, **params: Any) -> tuple[np.ndarray, ProcessingOperation]:
        """Apply a single operation and record it in history.

        Returns (result_array, operation_record).
        """
        if not hasattr(self, operation_name):
            raise ValueError(f"Unknown operation: {operation_name}")

        func = getattr(self, operation_name)
        input_array = np.asarray(array, dtype=np.float64)
        result = func(input_array, **params)

        op = ProcessingOperation(
            name=operation_name,
            parameters=params,
            applied_at=datetime.now(UTC).isoformat(),
            input_shape=tuple(int(x) for x in input_array.shape),
            output_shape=tuple(int(x) for x in np.asarray(result).shape),
        )
        self.history.append(op)
        logger.info("Applied operation %s with params %s", operation_name, params)
        return np.asarray(result, dtype=np.float64), op

    def apply_pipeline(
        self, array: np.ndarray, steps: list[tuple[str, dict[str, Any]]]
    ) -> tuple[np.ndarray, list[ProcessingOperation]]:
        """Chain multiple operations. Returns (final_array, operation_records)."""
        result = np.asarray(array, dtype=np.float64)
        records: list[ProcessingOperation] = []
        for op_name, params in steps:
            result, record = self.apply(result, op_name, **params)
            records.append(record)
        return result, records

    def clear_history(self) -> None:
        self.history = []
