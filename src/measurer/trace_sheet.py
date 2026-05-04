from __future__ import annotations

from measurer.measurement import Measurement, MeasurementResult
from measurer.roi import RoiSelection


TRACE_SHEET_HEADER = [
    "file",
    "group",
    "measurement type",
    "target ID",
    "status",
    "reason",
    "value_px",
    "x1_px",
    "y1_px",
    "x2_px",
    "y2_px",
    "scale_nm_per_px",
    "scale_source",
    "roi_type",
    "roi_x_px",
    "roi_y_px",
    "roi_width_px",
    "roi_height_px",
    "roi_shape_count",
    "refined_point_count",
    "fallback_point_count",
    "fallback_ratio",
]


def trace_sheet_row(
    *,
    file_name: str,
    group: str,
    measurement: Measurement,
    measurement_type: str,
    target_id: str,
    result: MeasurementResult,
    scale_source: str,
    scale_nm_per_px: float | None,
    roi: RoiSelection,
) -> list[object]:
    analysis_region = result.analysis_region
    refined_count, fallback_count, fallback_ratio = _refinement_summary(
        result, target_id
    )
    return [
        file_name,
        group,
        measurement_type,
        target_id,
        measurement.status,
        measurement.failure_reason,
        measurement.value_px if measurement.status == "success" else None,
        measurement.line.start.x,
        measurement.line.start.y,
        measurement.line.end.x,
        measurement.line.end.y,
        scale_nm_per_px,
        scale_source,
        _roi_type(roi),
        analysis_region.x,
        analysis_region.y,
        analysis_region.width,
        analysis_region.height,
        _roi_shape_count(roi),
        refined_count,
        fallback_count,
        fallback_ratio,
    ]


def _roi_type(roi: RoiSelection) -> str:
    if roi.is_empty:
        return "full_image"
    return "union"


def _roi_shape_count(roi: RoiSelection) -> int:
    return len(roi.rectangles) + len(roi.polygons)


def _refinement_summary(
    result: MeasurementResult, target_id: str
) -> tuple[int, int, float | None]:
    if not result.metal_islands:
        refined = result.refined_boundary.refined_point_count
        fallback = result.refined_boundary.fallback_point_count
        return refined, fallback, _fallback_ratio(refined, fallback)

    target_ids = target_id.split("-")
    boundaries = [
        metal.refined_boundary
        for metal in result.metal_islands
        if metal.id in target_ids
    ]
    if not boundaries and result.metal_islands:
        boundaries = [result.metal_islands[0].refined_boundary]

    refined = sum(boundary.refined_point_count for boundary in boundaries)
    fallback = sum(boundary.fallback_point_count for boundary in boundaries)
    return refined, fallback, _fallback_ratio(refined, fallback)


def _fallback_ratio(refined_count: int, fallback_count: int) -> float | None:
    total = refined_count + fallback_count
    if total == 0:
        return None
    return fallback_count / total
