from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import tifffile


@dataclass(frozen=True)
class ScaleResolution:
    source: str
    nm_per_px: float | None


@dataclass(frozen=True)
class RectRoi:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class QueueRow:
    path: Path
    file_name: str
    image: np.ndarray
    group: str = "Default"
    metadata_nm_per_px: float | None = None
    manual_nm_per_px: float | None = None
    scale_error: str = ""
    roi: RectRoi | None = None
    roi_status: str = "Full image"
    measure_status: str = "Pending"
    export_status: str = "Not exported"
    measurement_results: object | None = None
    measurement_debug: object | None = None


@dataclass(frozen=True)
class AddImagesSummary:
    added_count: int
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def skipped_count(self) -> int:
        return sum(self.skipped_reasons.values())

    @property
    def message(self) -> str:
        added_label = "image" if self.added_count == 1 else "images"
        if self.skipped_count == 0:
            return f"Added {self.added_count} {added_label}."

        skipped_details = ", ".join(
            f"{count} {reason}" for reason, count in self.skipped_reasons.items()
        )
        return (
            f"Added {self.added_count} {added_label}. "
            f"Skipped {self.skipped_count} files: {skipped_details}."
        )


class ImageQueue:
    def __init__(self) -> None:
        self.rows: list[QueueRow] = []
        self._paths: set[Path] = set()

    def add_images(self, paths: list[str | Path]) -> AddImagesSummary:
        added_count = 0
        skipped_reasons: dict[str, int] = {}

        for raw_path in paths:
            path = Path(raw_path).resolve()
            if path in self._paths:
                continue

            try:
                image = _read_tiff_image(path)
            except Exception:
                _count_skip(skipped_reasons, "failed to read image data")
                continue

            if not _is_supported_2d_image(image):
                _count_skip(skipped_reasons, "unsupported image shape")
                continue

            self.add_image_data(path, image)
            added_count += 1

        return AddImagesSummary(
            added_count=added_count, skipped_reasons=skipped_reasons
        )

    def add_image_data(
        self,
        path: str | Path,
        image: np.ndarray,
        metadata_nm_per_px: float | None = None,
    ) -> None:
        resolved_path = Path(path).resolve()
        row = QueueRow(
            path=resolved_path,
            file_name=resolved_path.name,
            image=image,
            metadata_nm_per_px=metadata_nm_per_px,
        )
        self.rows.append(row)
        self._paths.add(resolved_path)

    def set_group(self, row_indexes: list[int], group_name: str) -> bool:
        trimmed_name = group_name.strip()
        if trimmed_name == "":
            return False

        for row_index in row_indexes:
            if 0 <= row_index < len(self.rows):
                self.rows[row_index] = replace(
                    self.rows[row_index], group=trimmed_name
                )
        return True

    def set_manual_scale(self, row_index: int, scale_text: str) -> bool:
        if row_index < 0 or row_index >= len(self.rows):
            return False

        row = self.rows[row_index]
        if row.metadata_nm_per_px is not None:
            return False

        stripped_text = scale_text.strip()
        if stripped_text == "":
            self.rows[row_index] = replace(
                row, manual_nm_per_px=None, scale_error=""
            )
            return True

        try:
            scale = float(stripped_text)
        except ValueError:
            self.rows[row_index] = replace(
                row, scale_error="Enter a positive nm / pixel value."
            )
            return False

        if scale <= 0:
            self.rows[row_index] = replace(
                row, scale_error="Enter a positive nm / pixel value."
            )
            return False

        self.rows[row_index] = replace(
            row, manual_nm_per_px=scale, scale_error=""
        )
        return True

    def resolve_scale(self, row_index: int) -> ScaleResolution:
        row = self.rows[row_index]
        if row.metadata_nm_per_px is not None:
            return ScaleResolution(source="metadata", nm_per_px=row.metadata_nm_per_px)
        if row.manual_nm_per_px is not None:
            return ScaleResolution(source="manual", nm_per_px=row.manual_nm_per_px)
        return ScaleResolution(source="px", nm_per_px=None)

    def record_measurement_result(self, row_index: int, result: object) -> None:
        if row_index < 0 or row_index >= len(self.rows):
            return

        self.rows[row_index] = replace(
            self.rows[row_index],
            measure_status="Measured",
            export_status="Not exported",
            measurement_results=result,
            measurement_debug=result,
        )

    def record_measurement_failure(
        self, row_index: int, debug_result: object | None = None
    ) -> None:
        if row_index < 0 or row_index >= len(self.rows):
            return

        self.rows[row_index] = replace(
            self.rows[row_index],
            measure_status="Failed",
            export_status="Not exported",
            measurement_results=None,
            measurement_debug=debug_result,
        )

    def record_export_success(self, row_indexes: list[int]) -> None:
        for row_index in row_indexes:
            if 0 <= row_index < len(self.rows):
                self.rows[row_index] = replace(
                    self.rows[row_index],
                    export_status="Exported",
                )

    def set_roi(self, row_index: int, roi: RectRoi) -> bool:
        if row_index < 0 or row_index >= len(self.rows):
            return False

        row = self.rows[row_index]
        clamped_roi = _clamp_roi_to_image(roi, row.image)
        if clamped_roi is None:
            return False

        self.rows[row_index] = replace(
            row,
            roi=clamped_roi,
            roi_status="Custom ROI",
            measure_status="Pending",
            export_status="Not exported",
            measurement_results=None,
            measurement_debug=None,
        )
        return True

    def clear_roi(self, row_index: int) -> bool:
        if row_index < 0 or row_index >= len(self.rows):
            return False

        self.rows[row_index] = replace(
            self.rows[row_index],
            roi=None,
            roi_status="Full image",
            measure_status="Pending",
            export_status="Not exported",
            measurement_results=None,
            measurement_debug=None,
        )
        return True


def _read_tiff_image(path: Path) -> np.ndarray:
    with tifffile.TiffFile(path) as tiff:
        if len(tiff.pages) != 1:
            return np.asarray([])
        page = tiff.pages[0]
        image = tiff.asarray()

    if (
        image.ndim == 3
        and image.shape[-1] in (3, 4)
        and page.samplesperpixel in (3, 4)
    ):
        return _to_grayscale(image)
    return image


def _is_supported_2d_image(image: np.ndarray) -> bool:
    return image.ndim == 2


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    channels = image[..., :3].astype(np.float32)
    grayscale = (
        channels[..., 0] * 0.299
        + channels[..., 1] * 0.587
        + channels[..., 2] * 0.114
    )
    return np.rint(grayscale).astype(image.dtype)


def _count_skip(skipped_reasons: dict[str, int], reason: str) -> None:
    skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1


def _clamp_roi_to_image(roi: RectRoi, image: np.ndarray) -> RectRoi | None:
    image_height, image_width = image.shape
    left = max(0, roi.x)
    top = max(0, roi.y)
    right = min(image_width, roi.x + roi.width)
    bottom = min(image_height, roi.y + roi.height)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return RectRoi(x=left, y=top, width=width, height=height)
