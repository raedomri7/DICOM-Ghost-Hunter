"""Tests for the Image Processing Laboratory."""

from __future__ import annotations

import numpy as np
import pytest

from app.processing.operations import ImageProcessor


@pytest.fixture
def processor() -> ImageProcessor:
    return ImageProcessor()


@pytest.fixture
def test_array() -> np.ndarray:
    """A simple gradient test image."""
    return np.arange(256, dtype=np.float64).reshape(16, 16)


def test_normalize_minmax(processor, test_array):
    result = processor.normalize_minmax(test_array)
    assert np.isclose(result.min(), 0.0)
    assert np.isclose(result.max(), 1.0)
    assert result.shape == test_array.shape


def test_normalize_zscore(processor, test_array):
    result = processor.normalize_zscore(test_array)
    assert np.isclose(result.mean(), 0.0, atol=1e-6)
    assert np.isclose(result.std(), 1.0, atol=1e-6)


def test_normalize_percentile(processor, test_array):
    result = processor.normalize_percentile(test_array, low=10, high=90)
    assert np.isclose(result.min(), 0.0)
    assert np.isclose(result.max(), 1.0)


def test_contrast_adjust(processor, test_array):
    result = processor.contrast_adjust(test_array, factor=2.0)
    assert result.shape == test_array.shape
    # Contrast increased => wider spread
    assert result.std() > test_array.std()


def test_brightness_adjust(processor, test_array):
    result = processor.brightness_adjust(test_array, offset=100.0)
    assert np.isclose(result.mean(), test_array.mean() + 100.0)


def test_gamma_correction(processor, test_array):
    result = processor.gamma_correction(test_array, gamma=2.0)
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_invert(processor, test_array):
    result = processor.invert(test_array)
    assert np.isclose(result.min(), 0.0)
    assert np.isclose(result.max(), 1.0)


def test_clip(processor, test_array):
    result = processor.clip(test_array, low=50.0, high=200.0)
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_gaussian_filter(processor, test_array):
    result = processor.gaussian_filter(test_array, sigma=1.0)
    assert result.shape == test_array.shape


def test_median_filter(processor, test_array):
    result = processor.median_filter(test_array, size=3)
    assert result.shape == test_array.shape


def test_bilateral_filter(processor, test_array):
    result = processor.bilateral_filter(test_array, sigma_color=10.0, sigma_spatial=5.0)
    assert result.shape == test_array.shape


def test_histogram_equalization(processor, test_array):
    result = processor.histogram_equalization(test_array)
    assert result.shape == test_array.shape
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_clahe(processor, test_array):
    result = processor.clahe(test_array, clip_limit=2.0, tile_grid=8)
    assert result.shape == test_array.shape


def test_unsharp_masking(processor, test_array):
    result = processor.unsharp_masking(test_array, sigma=1.0, strength=1.0)
    assert result.shape == test_array.shape


def test_sobel(processor, test_array):
    result = processor.sobel(test_array)
    assert result.shape == test_array.shape


def test_prewitt(processor, test_array):
    result = processor.prewitt(test_array)
    assert result.shape == test_array.shape


def test_laplacian(processor, test_array):
    result = processor.laplacian(test_array)
    assert result.shape == test_array.shape


def test_canny(processor, test_array):
    result = processor.canny(test_array, low_threshold=50.0, high_threshold=150.0)
    assert result.shape == test_array.shape


def test_gradient_magnitude(processor, test_array):
    result = processor.gradient_magnitude(test_array)
    assert result.shape == test_array.shape


def test_erosion_dilation(processor, test_array):
    eroded = processor.erosion(test_array, iterations=1)
    dilated = processor.dilation(test_array, iterations=1)
    assert eroded.shape == test_array.shape
    assert dilated.shape == test_array.shape


def test_opening_closing(processor, test_array):
    opened = processor.opening(test_array, iterations=1)
    closed = processor.closing(test_array, iterations=1)
    assert opened.shape == test_array.shape
    assert closed.shape == test_array.shape


def test_morphological_gradient(processor, test_array):
    result = processor.morphological_gradient(test_array, iterations=1)
    assert result.shape == test_array.shape


def test_fft_spectrum(processor, test_array):
    result = processor.fft_spectrum(test_array)
    assert result.shape == test_array.shape


def test_lowpass_filter(processor, test_array):
    result = processor.lowpass_filter(test_array, cutoff=30.0)
    assert result.shape == test_array.shape


def test_highpass_filter(processor, test_array):
    result = processor.highpass_filter(test_array, cutoff=30.0)
    assert result.shape == test_array.shape


def test_apply_pipeline(processor, test_array):
    steps = [
        ("normalize_minmax", {}),
        ("gaussian_filter", {"sigma": 1.0}),
        ("sobel", {}),
    ]
    result, records = processor.apply_pipeline(test_array, steps)
    assert result.shape == test_array.shape
    assert len(records) == 3
    assert records[0].name == "normalize_minmax"
    assert records[1].name == "gaussian_filter"
    assert records[2].name == "sobel"


def test_apply_single_operation(processor, test_array):
    result, record = processor.apply(test_array, "gaussian_filter", sigma=2.0)
    assert result.shape == test_array.shape
    assert record.name == "gaussian_filter"
    assert record.parameters == {"sigma": 2.0}


def test_available_operations(processor):
    ops = processor.available_operations()
    assert "gaussian_filter" in ops
    assert "sobel" in ops
    assert "clahe" in ops


def test_clear_history(processor, test_array):
    processor.apply(test_array, "gaussian_filter", sigma=1.0)
    assert len(processor.history) == 1
    processor.clear_history()
    assert len(processor.history) == 0


def test_input_not_mutated(processor, test_array):
    original = test_array.copy()
    processor.normalize_minmax(test_array)
    assert np.array_equal(test_array, original)


def test_unknown_operation_raises(processor, test_array):
    with pytest.raises(ValueError):
        processor.apply(test_array, "nonexistent_operation")
