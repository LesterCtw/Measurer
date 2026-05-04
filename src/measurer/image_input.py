from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile


@dataclass(frozen=True)
class LoadedImage:
    image: np.ndarray
    metadata_nm_per_px: float | None = None


def read_stem_zc_image(path: Path) -> LoadedImage:
    if path.suffix.lower() == ".dm3":
        return _read_dm3_image(path)
    return _read_tiff_image(path)


def is_supported_2d_image(image: np.ndarray) -> bool:
    return image.ndim == 2


def _read_tiff_image(path: Path) -> LoadedImage:
    with tifffile.TiffFile(path) as tiff:
        if len(tiff.pages) != 1:
            return LoadedImage(image=np.asarray([]))
        page = tiff.pages[0]
        image = tiff.asarray()
        metadata_nm_per_px = _metadata_nm_per_px_from_tiff_page(page)

    if (
        image.ndim == 3
        and image.shape[-1] in (3, 4)
        and page.samplesperpixel in (3, 4)
    ):
        image = _to_grayscale(image)
    return LoadedImage(image=image, metadata_nm_per_px=metadata_nm_per_px)


def _metadata_nm_per_px_from_tiff_page(page: tifffile.TiffPage) -> float | None:
    try:
        resolution_unit = int(page.tags["ResolutionUnit"].value)
        x_resolution = _ratio_to_float(page.tags["XResolution"].value)
        y_resolution = _ratio_to_float(page.tags["YResolution"].value)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None

    if x_resolution <= 0 or y_resolution <= 0:
        return None
    if not np.allclose([x_resolution, y_resolution], x_resolution):
        return None

    if resolution_unit == 2:
        nm_per_unit = 25_400_000.0
    elif resolution_unit == 3:
        nm_per_unit = 10_000_000.0
    else:
        return None
    return nm_per_unit / x_resolution


def _ratio_to_float(value: object) -> float:
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        return float(numerator) / float(denominator)
    return float(value)


def _read_dm3_image(path: Path) -> LoadedImage:
    from rsciio import digitalmicrograph

    signals = digitalmicrograph.file_reader(str(path))
    if len(signals) == 0:
        return LoadedImage(image=np.asarray([]))

    signal = signals[0]
    image = np.asarray(signal["data"])
    return LoadedImage(
        image=image,
        metadata_nm_per_px=_metadata_nm_per_px_from_axes(signal.get("axes", [])),
    )


def _metadata_nm_per_px_from_axes(axes: object) -> float | None:
    if not isinstance(axes, list):
        return None

    nm_scales: list[float] = []
    for axis in axes:
        if not isinstance(axis, dict):
            continue
        units = str(axis.get("units", "")).strip().lower()
        if units not in {"nm", "nanometer", "nanometers"}:
            continue
        try:
            scale = float(axis["scale"])
        except (KeyError, TypeError, ValueError):
            continue
        if scale > 0:
            nm_scales.append(scale)

    if len(nm_scales) < 2:
        return None
    if not np.allclose(nm_scales, nm_scales[0]):
        return None
    return nm_scales[0]


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    channels = image[..., :3].astype(np.float32)
    grayscale = (
        channels[..., 0] * 0.299
        + channels[..., 1] * 0.587
        + channels[..., 2] * 0.114
    )
    return np.rint(grayscale).astype(image.dtype)
