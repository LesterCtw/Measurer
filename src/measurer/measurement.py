from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np

from measurer.image_queue import RectRoi


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class MeasurementLine:
    start: Point
    end: Point


@dataclass(frozen=True)
class Measurement:
    name: str
    value_px: float
    line: MeasurementLine


@dataclass(frozen=True)
class RefinedBoundary:
    points: list[Point]


@dataclass(frozen=True)
class MeasurementResult:
    status: str
    analysis_region: RectRoi
    refined_boundary: RefinedBoundary
    measurements: dict[str, Measurement]


def measure_image(image: np.ndarray, roi: RectRoi | None) -> MeasurementResult:
    analysis_region = _analysis_region_for(image, roi)
    region = image[
        analysis_region.y : analysis_region.y + analysis_region.height,
        analysis_region.x : analysis_region.x + analysis_region.width,
    ]
    threshold = _otsu_threshold(region)
    mask = region > threshold
    if not np.any(mask):
        return MeasurementResult(
            status="failed",
            analysis_region=analysis_region,
            refined_boundary=RefinedBoundary(points=[]),
            measurements={},
        )

    ys, xs = np.nonzero(mask)
    global_ys = ys + analysis_region.y
    global_xs = xs + analysis_region.x
    spans = _row_spans(global_xs, global_ys)
    boundary = RefinedBoundary(points=_closed_boundary_from_spans(spans))
    measurements = _measure_single_metal_island(spans, mask, analysis_region)
    return MeasurementResult(
        status="success",
        analysis_region=analysis_region,
        refined_boundary=boundary,
        measurements=measurements,
    )


def _analysis_region_for(image: np.ndarray, roi: RectRoi | None) -> RectRoi:
    image_height, image_width = image.shape
    if roi is None:
        return RectRoi(x=0, y=0, width=image_width, height=image_height)

    left = max(0, roi.x)
    top = max(0, roi.y)
    right = min(image_width, roi.x + roi.width)
    bottom = min(image_height, roi.y + roi.height)
    return RectRoi(x=left, y=top, width=right - left, height=bottom - top)


def _otsu_threshold(region: np.ndarray) -> float:
    values = np.asarray(region, dtype=np.float64)
    counts, bin_edges = np.histogram(values, bins=256)
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    total = counts.sum()
    if total == 0:
        return 0.0

    weight_low = np.cumsum(counts)
    weight_high = total - weight_low
    sum_low = np.cumsum(counts * centers)
    sum_total = sum_low[-1]
    valid = (weight_low > 0) & (weight_high > 0)
    score = np.zeros_like(centers)
    mean_low = np.zeros_like(centers)
    mean_high = np.zeros_like(centers)
    mean_low[valid] = sum_low[valid] / weight_low[valid]
    mean_high[valid] = (sum_total - sum_low[valid]) / weight_high[valid]
    score[valid] = weight_low[valid] * weight_high[valid] * (
        mean_low[valid] - mean_high[valid]
    ) ** 2
    return float(centers[int(np.argmax(score))])


def _row_spans(xs: np.ndarray, ys: np.ndarray) -> dict[int, tuple[int, int]]:
    spans: dict[int, tuple[int, int]] = {}
    for y in sorted(set(int(value) for value in ys)):
        row_xs = xs[ys == y]
        spans[y] = (int(np.min(row_xs)), int(np.max(row_xs)))
    return spans


def _closed_boundary_from_spans(spans: dict[int, tuple[int, int]]) -> list[Point]:
    left_points = [Point(x=spans[y][0], y=y) for y in sorted(spans)]
    right_points = [Point(x=spans[y][1], y=y) for y in sorted(spans, reverse=True)]
    points = left_points + right_points
    if points:
        points.append(points[0])
    return points


def _measure_single_metal_island(
    spans: dict[int, tuple[int, int]],
    mask: np.ndarray,
    analysis_region: RectRoi,
) -> dict[str, Measurement]:
    rows = sorted(spans)
    min_y = rows[0]
    max_y = rows[-1]
    height = max_y - min_y + 1
    top_row_count = max(1, ceil(height * 0.2))
    bottom_row_count = max(1, ceil(height * 0.1))

    tcd_rows = [y for y in rows if y <= min_y + top_row_count - 1]
    bcd_rows = [y for y in rows if y >= max_y - bottom_row_count + 1]
    tcd_y, tcd_width = _widest_row(spans, tcd_rows)
    bcd_y, bcd_width = _widest_row(spans, bcd_rows)
    height_x, height_value = _tallest_column(mask, analysis_region)

    return {
        "TCD": Measurement(
            name="TCD",
            value_px=float(tcd_width),
            line=MeasurementLine(
                start=Point(x=spans[tcd_y][0], y=tcd_y),
                end=Point(x=spans[tcd_y][1], y=tcd_y),
            ),
        ),
        "BCD": Measurement(
            name="BCD",
            value_px=float(bcd_width),
            line=MeasurementLine(
                start=Point(x=spans[bcd_y][0], y=bcd_y),
                end=Point(x=spans[bcd_y][1], y=bcd_y),
            ),
        ),
        "Height": Measurement(
            name="Height",
            value_px=float(height_value),
            line=MeasurementLine(
                start=Point(x=height_x, y=min_y),
                end=Point(x=height_x, y=max_y),
            ),
        ),
    }


def _widest_row(
    spans: dict[int, tuple[int, int]], rows: list[int]
) -> tuple[int, int]:
    return max(
        ((y, spans[y][1] - spans[y][0] + 1) for y in rows),
        key=lambda item: item[1],
    )


def _tallest_column(mask: np.ndarray, analysis_region: RectRoi) -> tuple[int, int]:
    column_counts = np.sum(mask, axis=0)
    local_x = int(np.argmax(column_counts))
    return analysis_region.x + local_x, int(column_counts[local_x])
