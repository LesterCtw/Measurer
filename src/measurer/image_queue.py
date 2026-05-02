from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import tifffile


@dataclass(frozen=True)
class QueueRow:
    path: Path
    file_name: str
    image: np.ndarray
    group: str = "Default"
    roi_status: str = "Full image"
    measure_status: str = "Pending"
    export_status: str = "Not exported"


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

            row = QueueRow(path=path, file_name=path.name, image=image)
            self.rows.append(row)
            self._paths.add(path)
            added_count += 1

        return AddImagesSummary(
            added_count=added_count, skipped_reasons=skipped_reasons
        )


def _read_tiff_image(path: Path) -> np.ndarray:
    with tifffile.TiffFile(path) as tiff:
        if len(tiff.pages) != 1:
            return np.asarray([])
        page = tiff.pages[0]
        image = tiff.asarray()

    if image.ndim == 3 and image.shape[-1] in (3, 4) and page.samplesperpixel in (3, 4):
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
