from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import ceil

import numpy as np

from measurer.roi import (
    RectRoi,
    RoiSelection,
    clamp_rect_roi_to_image,
    roi_union_mask,
)

HARD_MIN_COMPONENT_AREA_PX = 100
MIN_AREA_RATIO_TO_MEDIAN = 0.03
BOUNDARY_TOUCH_MARGIN_PX = 1
BOUNDARY_PROFILE_HALF_LENGTH_PX = 12
BOUNDARY_PROFILE_AVERAGING_WIDTH_PX = 5
REFINEMENT_SAMPLING_STEP_PX = 2
MIN_REFINEMENT_SIDE_SAMPLES = 4
MIN_REFINEMENT_CONTRAST = 5.0


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class MeasurementConfig:
    hard_min_component_area_px: int = HARD_MIN_COMPONENT_AREA_PX
    min_area_ratio_to_median: float = MIN_AREA_RATIO_TO_MEDIAN
    boundary_touch_margin_px: int = BOUNDARY_TOUCH_MARGIN_PX
    boundary_profile_half_length_px: int = BOUNDARY_PROFILE_HALF_LENGTH_PX
    boundary_profile_averaging_width_px: int = BOUNDARY_PROFILE_AVERAGING_WIDTH_PX
    refinement_sampling_step_px: int = REFINEMENT_SAMPLING_STEP_PX
    min_refinement_side_samples: int = MIN_REFINEMENT_SIDE_SAMPLES
    min_refinement_contrast: float = MIN_REFINEMENT_CONTRAST


@dataclass(frozen=True)
class MeasurementLine:
    start: Point
    end: Point


@dataclass(frozen=True)
class Measurement:
    name: str
    value_px: float
    line: MeasurementLine
    status: str = "success"
    failure_reason: str = ""


@dataclass(frozen=True)
class BoundaryPoint:
    point: Point
    status: str


@dataclass(frozen=True)
class RefinedBoundary:
    points: list[Point]
    point_statuses: list[str] = field(default_factory=list)

    @property
    def refined_point_count(self) -> int:
        return self.point_statuses.count("refined")

    @property
    def fallback_point_count(self) -> int:
        return self.point_statuses.count("fallback_rough")

    @property
    def fallback_ratio(self) -> float:
        if not self.point_statuses:
            return 0.0
        return self.fallback_point_count / len(self.point_statuses)


@dataclass(frozen=True)
class ComponentDiagnostic:
    area_px: int
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class DetectionDiagnostics:
    rough_mask: np.ndarray
    kept_candidates: list[ComponentDiagnostic]
    excluded_small_components: list[ComponentDiagnostic]
    excluded_boundary_touch_components: list[ComponentDiagnostic]


@dataclass(frozen=True)
class MetalIsland:
    id: str
    refined_boundary: RefinedBoundary
    measurements: dict[str, Measurement]


@dataclass(frozen=True)
class SpacePairDiagnostic:
    pair_name: str
    measurement_type: str
    reason: str


@dataclass(frozen=True)
class _VerticalGap:
    value_px: float
    line: MeasurementLine


@dataclass(frozen=True)
class MeasurementResult:
    status: str
    analysis_region: RectRoi
    refined_boundary: RefinedBoundary
    measurements: dict[str, Measurement]
    failure_reason: str = ""
    detection: DetectionDiagnostics | None = None
    metal_islands: list[MetalIsland] = field(default_factory=list)
    rejected_space_pairs: list[SpacePairDiagnostic] = field(default_factory=list)


def measure_image(
    image: np.ndarray,
    roi: RectRoi | RoiSelection | None,
    config: MeasurementConfig | None = None,
) -> MeasurementResult:
    config = config or MeasurementConfig()
    analysis_region = _analysis_region_for(image, roi)
    analysis_mask = _analysis_mask_for(image, roi, analysis_region)
    region = image[
        analysis_region.y : analysis_region.y + analysis_region.height,
        analysis_region.x : analysis_region.x + analysis_region.width,
    ]
    threshold = _otsu_threshold(region[analysis_mask])
    mask = (region > threshold) & analysis_mask
    detection, candidates = _detect_metal_candidates(mask, analysis_mask, config)
    if not candidates:
        return MeasurementResult(
            status="failed",
            analysis_region=analysis_region,
            refined_boundary=RefinedBoundary(points=[]),
            measurements={},
            failure_reason="No metal candidates",
            detection=detection,
        )

    metal_islands = _measure_metal_islands(
        image=image,
        candidates=candidates,
        analysis_region=analysis_region,
        analysis_mask=analysis_mask,
        config=config,
    )
    measurements = _flatten_metal_measurements(metal_islands)
    horizontal_measurements, horizontal_rejected = _measure_horizontal_spaces(
        metal_islands
    )
    vertical_measurements, vertical_rejected = _measure_vertical_spaces(metal_islands)
    measurements.update(horizontal_measurements)
    measurements.update(vertical_measurements)
    return MeasurementResult(
        status="success",
        analysis_region=analysis_region,
        refined_boundary=metal_islands[0].refined_boundary,
        measurements=measurements,
        detection=detection,
        metal_islands=metal_islands,
        rejected_space_pairs=horizontal_rejected + vertical_rejected,
    )


def _analysis_region_for(
    image: np.ndarray, roi: RectRoi | RoiSelection | None
) -> RectRoi:
    image_height, image_width = image.shape
    if roi is None or (isinstance(roi, RoiSelection) and roi.is_empty):
        return RectRoi(x=0, y=0, width=image_width, height=image_height)

    if isinstance(roi, RoiSelection):
        bounding_box = roi.bounding_box_for_image(image)
        if bounding_box is None:
            return RectRoi(x=0, y=0, width=image_width, height=image_height)

        clamped_roi = clamp_rect_roi_to_image(bounding_box, image)
        if clamped_roi is None:
            return RectRoi(x=0, y=0, width=image_width, height=image_height)
        return clamped_roi

    clamped_roi = clamp_rect_roi_to_image(roi, image)
    if clamped_roi is None:
        return RectRoi(x=0, y=0, width=0, height=0)
    return clamped_roi


def _analysis_mask_for(
    image: np.ndarray,
    roi: RectRoi | RoiSelection | None,
    analysis_region: RectRoi,
) -> np.ndarray:
    mask = np.ones((analysis_region.height, analysis_region.width), dtype=bool)
    if roi is None or isinstance(roi, RectRoi) or (
        isinstance(roi, RoiSelection) and roi.is_empty
    ):
        return mask

    return roi_union_mask(roi, image, analysis_region)


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


def _detect_metal_candidates(
    mask: np.ndarray, analysis_mask: np.ndarray, config: MeasurementConfig
) -> tuple[DetectionDiagnostics, list[_Component]]:
    components = _connected_components(mask)
    boundary_mask = _analysis_boundary_margin_mask(
        analysis_mask, config.boundary_touch_margin_px
    )
    hard_kept: list[_Component] = []
    excluded_small: list[_Component] = []
    for component in components:
        if component.area_px < config.hard_min_component_area_px:
            excluded_small.append(component)
        else:
            hard_kept.append(component)

    if hard_kept:
        median_area = float(np.median([component.area_px for component in hard_kept]))
        relative_min_area = median_area * config.min_area_ratio_to_median
        area_kept = []
        for component in hard_kept:
            if component.area_px < relative_min_area:
                excluded_small.append(component)
            else:
                area_kept.append(component)
    else:
        area_kept = []

    kept_candidates: list[_Component] = []
    excluded_boundary_touch: list[_Component] = []
    for component in area_kept:
        if _touches_analysis_boundary(component, boundary_mask):
            excluded_boundary_touch.append(component)
        else:
            kept_candidates.append(component)

    diagnostics = DetectionDiagnostics(
        rough_mask=mask.copy(),
        kept_candidates=[_component_diagnostic(component) for component in kept_candidates],
        excluded_small_components=[
            _component_diagnostic(component) for component in excluded_small
        ],
        excluded_boundary_touch_components=[
            _component_diagnostic(component) for component in excluded_boundary_touch
        ],
    )

    if not kept_candidates:
        return diagnostics, []

    return diagnostics, kept_candidates


@dataclass(frozen=True)
class _Component:
    local_xs: np.ndarray
    local_ys: np.ndarray

    @property
    def area_px(self) -> int:
        return int(self.local_xs.size)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (
            int(np.min(self.local_xs)),
            int(np.min(self.local_ys)),
            int(np.max(self.local_xs)),
            int(np.max(self.local_ys)),
        )


def _connected_components(mask: np.ndarray) -> list[_Component]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    components: list[_Component] = []

    for start_y, start_x in zip(*np.nonzero(mask), strict=False):
        if visited[start_y, start_x]:
            continue

        stack = [(int(start_x), int(start_y))]
        xs: list[int] = []
        ys: list[int] = []
        visited[start_y, start_x] = True
        while stack:
            x, y = stack.pop()
            xs.append(x)
            ys.append(y)
            for next_x, next_y in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if (
                    0 <= next_x < width
                    and 0 <= next_y < height
                    and mask[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    stack.append((next_x, next_y))

        components.append(
            _Component(
                local_xs=np.asarray(xs, dtype=np.int32),
                local_ys=np.asarray(ys, dtype=np.int32),
            )
        )

    return components


def _touches_analysis_boundary(
    component: _Component, boundary_mask: np.ndarray
) -> bool:
    return bool(np.any(boundary_mask[component.local_ys, component.local_xs]))


def _analysis_boundary_margin_mask(
    analysis_mask: np.ndarray, boundary_touch_margin_px: int
) -> np.ndarray:
    selected = analysis_mask.astype(bool, copy=False)
    padded = np.pad(selected, 1, mode="constant", constant_values=False)
    interior = (
        padded[1:-1, :-2]
        & padded[1:-1, 2:]
        & padded[:-2, 1:-1]
        & padded[2:, 1:-1]
    )
    boundary = selected & ~interior
    expanded = boundary
    for _ in range(max(0, boundary_touch_margin_px)):
        padded_expanded = np.pad(expanded, 1, mode="constant", constant_values=False)
        expanded = selected & (
            padded_expanded[:-2, :-2]
            | padded_expanded[:-2, 1:-1]
            | padded_expanded[:-2, 2:]
            | padded_expanded[1:-1, :-2]
            | padded_expanded[1:-1, 1:-1]
            | padded_expanded[1:-1, 2:]
            | padded_expanded[2:, :-2]
            | padded_expanded[2:, 1:-1]
            | padded_expanded[2:, 2:]
        )
    return expanded


def _component_diagnostic(component: _Component) -> ComponentDiagnostic:
    return ComponentDiagnostic(area_px=component.area_px, bbox=component.bbox)


def _measure_metal_islands(
    image: np.ndarray,
    candidates: list[_Component],
    analysis_region: RectRoi,
    analysis_mask: np.ndarray,
    config: MeasurementConfig,
) -> list[MetalIsland]:
    measured: list[tuple[_Component, RefinedBoundary, dict[str, Measurement]]] = []
    for candidate in candidates:
        candidate_mask = np.zeros(
            (
                analysis_region.height,
                analysis_region.width,
            ),
            dtype=bool,
        )
        candidate_mask[candidate.local_ys, candidate.local_xs] = True
        global_ys = candidate.local_ys + analysis_region.y
        global_xs = candidate.local_xs + analysis_region.x
        spans = _row_spans(global_xs, global_ys)
        boundary = _refined_boundary_from_spans(
            image, spans, analysis_region, analysis_mask, config
        )
        measurements = _measure_single_metal_island(
            spans, candidate_mask, analysis_region
        )
        measured.append((candidate, boundary, measurements))

    ordered_candidates = _assign_metal_ids([candidate for candidate, _, _ in measured])
    metal_ids = {
        id(candidate): f"M{index:03d}"
        for index, candidate in enumerate(ordered_candidates, start=1)
    }
    metal_islands = [
        MetalIsland(
            id=metal_ids[id(candidate)],
            refined_boundary=boundary,
            measurements=measurements,
        )
        for candidate, boundary, measurements in measured
    ]
    return sorted(metal_islands, key=lambda metal: metal.id)


def _assign_metal_ids(candidates: list[_Component]) -> list[_Component]:
    heights = [
        candidate.bbox[3] - candidate.bbox[1] + 1
        for candidate in candidates
    ]
    row_tolerance = max(1.0, float(np.median(heights)))
    rows: list[list[_Component]] = []

    for candidate in sorted(candidates, key=lambda item: _component_center(item)[1]):
        center_y = _component_center(candidate)[1]
        for row in rows:
            row_center_y = float(
                np.median([_component_center(item)[1] for item in row])
            )
            if abs(center_y - row_center_y) <= row_tolerance:
                row.append(candidate)
                break
        else:
            rows.append([candidate])

    ordered_candidates: list[_Component] = []
    for row in sorted(
        rows,
        key=lambda items: float(
            np.median([_component_center(item)[1] for item in items])
        ),
    ):
        ordered_candidates.extend(
            sorted(row, key=lambda item: _component_center(item)[0])
        )

    return ordered_candidates


def _component_center(component: _Component) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = component.bbox
    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


def _flatten_metal_measurements(
    metal_islands: list[MetalIsland],
) -> dict[str, Measurement]:
    if len(metal_islands) == 1:
        return metal_islands[0].measurements

    flattened: dict[str, Measurement] = {}
    for metal in metal_islands:
        for measurement_name, measurement in metal.measurements.items():
            key = f"{metal.id} {measurement_name}"
            flattened[key] = replace(measurement, name=key)
    return flattened


def _measure_horizontal_spaces(
    metal_islands: list[MetalIsland],
) -> tuple[dict[str, Measurement], list[SpacePairDiagnostic]]:
    measurements: dict[str, Measurement] = {}
    rejected_pairs: list[SpacePairDiagnostic] = []
    for row in _group_metal_rows(metal_islands):
        ordered_row = sorted(
            row, key=lambda metal: _boundary_center(metal.refined_boundary)[0]
        )
        for left, right in zip(ordered_row, ordered_row[1:], strict=False):
            left_bbox = _boundary_bbox(left.refined_boundary)
            right_bbox = _boundary_bbox(right.refined_boundary)
            name = f"{left.id}-{right.id} Horizontal Space"
            if not _has_required_overlap(
                left_bbox[1],
                left_bbox[3],
                right_bbox[1],
                right_bbox[3],
            ):
                rejected_pairs.append(
                    SpacePairDiagnostic(
                        pair_name=f"{left.id}-{right.id}",
                        measurement_type="Horizontal Space",
                        reason="Insufficient y-overlap.",
                    )
                )
                continue

            left_endpoint, right_endpoint = _horizontal_space_display_endpoints(
                left,
                right,
            )
            measurements[name] = Measurement(
                name=name,
                value_px=float(right_endpoint.x - left_endpoint.x),
                line=MeasurementLine(
                    start=left_endpoint,
                    end=right_endpoint,
                ),
            )
    return measurements, rejected_pairs


def _measure_vertical_spaces(
    metal_islands: list[MetalIsland],
) -> tuple[dict[str, Measurement], list[SpacePairDiagnostic]]:
    measurements: dict[str, Measurement] = {}
    rejected_pairs: list[SpacePairDiagnostic] = []
    for column in _group_metal_columns(metal_islands):
        ordered_column = sorted(
            column, key=lambda metal: _boundary_center(metal.refined_boundary)[1]
        )
        for upper, lower in zip(ordered_column, ordered_column[1:], strict=False):
            upper_bbox = _boundary_bbox(upper.refined_boundary)
            lower_bbox = _boundary_bbox(lower.refined_boundary)
            name = f"{upper.id}-{lower.id} Vertical Space"
            if not _has_required_overlap(
                upper_bbox[0],
                upper_bbox[2],
                lower_bbox[0],
                lower_bbox[2],
            ):
                rejected_pairs.append(
                    SpacePairDiagnostic(
                        pair_name=f"{upper.id}-{lower.id}",
                        measurement_type="Vertical Space",
                        reason="Insufficient x-overlap.",
                    )
                )
                continue

            gap = _minimum_vertical_boundary_gap(
                upper.refined_boundary, lower.refined_boundary
            )
            if gap is None:
                measurements[name] = Measurement(
                    name=name,
                    value_px=float("nan"),
                    line=_fallback_vertical_space_line(upper_bbox, lower_bbox),
                    status="failed",
                    failure_reason=(
                        "Could not calculate vertical boundary intersections."
                    ),
                )
                continue

            measurements[name] = Measurement(
                name=name,
                value_px=gap.value_px,
                line=gap.line,
            )
    return measurements, rejected_pairs


def _fallback_vertical_space_line(
    upper_bbox: tuple[int, int, int, int],
    lower_bbox: tuple[int, int, int, int],
) -> MeasurementLine:
    x = round(
        (max(upper_bbox[0], lower_bbox[0]) + min(upper_bbox[2], lower_bbox[2]))
        / 2
    )
    return MeasurementLine(
        start=Point(x=x, y=upper_bbox[3]),
        end=Point(x=x, y=lower_bbox[1]),
    )


def _minimum_vertical_boundary_gap(
    upper_boundary: RefinedBoundary, lower_boundary: RefinedBoundary
) -> _VerticalGap | None:
    upper_bbox = _boundary_bbox(upper_boundary)
    lower_bbox = _boundary_bbox(lower_boundary)
    overlap_min_x = max(upper_bbox[0], lower_bbox[0])
    overlap_max_x = min(upper_bbox[2], lower_bbox[2])
    best_gap: _VerticalGap | None = None
    target_x = (overlap_min_x + overlap_max_x) / 2
    for x in range(overlap_min_x, overlap_max_x + 1):
        upper_intersections = _vertical_boundary_intersections(upper_boundary, x)
        lower_intersections = _vertical_boundary_intersections(lower_boundary, x)
        if not upper_intersections or not lower_intersections:
            continue

        upper_bottom_y = max(upper_intersections)
        lower_top_y = min(lower_intersections)
        gap_value = max(0.0, lower_top_y - upper_bottom_y - 1)
        gap = _VerticalGap(
            value_px=gap_value,
            line=MeasurementLine(
                start=Point(x=x, y=round(upper_bottom_y + 1)),
                end=Point(x=x, y=round(lower_top_y - 1)),
            ),
        )
        if best_gap is None or gap.value_px < best_gap.value_px:
            best_gap = gap
        elif gap.value_px == best_gap.value_px and abs(x - target_x) <= abs(
            best_gap.line.start.x - target_x
        ):
            best_gap = gap

    return best_gap


def _vertical_boundary_intersections(
    boundary: RefinedBoundary, x: int
) -> list[float]:
    intersections: list[float] = []
    for start, end in zip(boundary.points, boundary.points[1:], strict=False):
        min_x = min(start.x, end.x)
        max_x = max(start.x, end.x)
        if not (min_x <= x <= max_x):
            continue

        if start.x == end.x:
            if x == start.x:
                intersections.extend([float(start.y), float(end.y)])
            continue

        fraction = (x - start.x) / (end.x - start.x)
        intersections.append(start.y + fraction * (end.y - start.y))
    return intersections


def _group_metal_rows(metal_islands: list[MetalIsland]) -> list[list[MetalIsland]]:
    if not metal_islands:
        return []

    heights = [
        _boundary_bbox(metal.refined_boundary)[3]
        - _boundary_bbox(metal.refined_boundary)[1]
        + 1
        for metal in metal_islands
    ]
    tolerance = max(1.0, float(np.median(heights)))
    rows: list[list[MetalIsland]] = []
    for metal in sorted(
        metal_islands, key=lambda item: _boundary_center(item.refined_boundary)[1]
    ):
        center_y = _boundary_center(metal.refined_boundary)[1]
        for row in rows:
            row_center_y = float(
                np.median(
                    [_boundary_center(item.refined_boundary)[1] for item in row]
                )
            )
            if abs(center_y - row_center_y) <= tolerance:
                row.append(metal)
                break
        else:
            rows.append([metal])
    return rows


def _group_metal_columns(metal_islands: list[MetalIsland]) -> list[list[MetalIsland]]:
    if not metal_islands:
        return []

    widths = [
        _boundary_bbox(metal.refined_boundary)[2]
        - _boundary_bbox(metal.refined_boundary)[0]
        + 1
        for metal in metal_islands
    ]
    tolerance = max(1.0, float(np.median(widths)))
    columns: list[list[MetalIsland]] = []
    for metal in sorted(
        metal_islands, key=lambda item: _boundary_center(item.refined_boundary)[0]
    ):
        center_x = _boundary_center(metal.refined_boundary)[0]
        for column in columns:
            column_center_x = float(
                np.median(
                    [_boundary_center(item.refined_boundary)[0] for item in column]
                )
            )
            if abs(center_x - column_center_x) <= tolerance:
                column.append(metal)
                break
        else:
            columns.append([metal])
    return columns


def _has_required_overlap(
    first_min: int, first_max: int, second_min: int, second_max: int
) -> bool:
    overlap = min(first_max, second_max) - max(first_min, second_min) + 1
    first_size = first_max - first_min + 1
    second_size = second_max - second_min + 1
    return overlap > min(first_size, second_size) * 0.3


def _boundary_bbox(boundary: RefinedBoundary) -> tuple[int, int, int, int]:
    xs = [point.x for point in boundary.points]
    ys = [point.y for point in boundary.points]
    return min(xs), min(ys), max(xs), max(ys)


def _boundary_center(boundary: RefinedBoundary) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = _boundary_bbox(boundary)
    return (min_x + max_x) / 2, (min_y + max_y) / 2


def _horizontal_space_display_endpoints(
    left: MetalIsland, right: MetalIsland
) -> tuple[Point, Point]:
    left_bbox = _boundary_bbox(left.refined_boundary)
    right_bbox = _boundary_bbox(right.refined_boundary)
    y = _horizontal_space_display_y(left, right)
    return Point(x=left_bbox[2], y=y), Point(x=right_bbox[0], y=y)


def _horizontal_space_display_y(left: MetalIsland, right: MetalIsland) -> int:
    left_tcd = left.measurements["TCD"].line
    right_tcd = right.measurements["TCD"].line
    return round((left_tcd.end.y + right_tcd.start.y) / 2)


def _refined_boundary_from_spans(
    image: np.ndarray,
    spans: dict[int, tuple[int, int]],
    analysis_region: RectRoi,
    analysis_mask: np.ndarray,
    config: MeasurementConfig,
) -> RefinedBoundary:
    boundary_points: list[BoundaryPoint] = []
    for y in sorted(spans):
        rough_point = Point(x=spans[y][0], y=y)
        boundary_points.append(
            _refine_boundary_point(
                image=image,
                rough_point=rough_point,
                inside_direction=(1, 0),
                analysis_region=analysis_region,
                analysis_mask=analysis_mask,
                config=config,
            )
        )

    for y in sorted(spans, reverse=True):
        rough_point = Point(x=spans[y][1], y=y)
        boundary_points.append(
            _refine_boundary_point(
                image=image,
                rough_point=rough_point,
                inside_direction=(-1, 0),
                analysis_region=analysis_region,
                analysis_mask=analysis_mask,
                config=config,
            )
        )

    if boundary_points:
        boundary_points.append(boundary_points[0])

    return RefinedBoundary(
        points=[boundary_point.point for boundary_point in boundary_points],
        point_statuses=[
            boundary_point.status for boundary_point in boundary_points
        ],
    )


def _refine_boundary_point(
    image: np.ndarray,
    rough_point: Point,
    inside_direction: tuple[int, int],
    analysis_region: RectRoi,
    analysis_mask: np.ndarray,
    config: MeasurementConfig,
) -> BoundaryPoint:
    profile = _sample_boundary_profile(
        image=image,
        rough_point=rough_point,
        inside_direction=inside_direction,
        analysis_region=analysis_region,
        analysis_mask=analysis_mask,
        config=config,
    )
    outside_samples = [value for offset, value in profile if offset < 0]
    inside_samples = [value for offset, value in profile if offset > 0]
    if (
        len(outside_samples) < config.min_refinement_side_samples
        or len(inside_samples) < config.min_refinement_side_samples
    ):
        return BoundaryPoint(point=rough_point, status="fallback_rough")

    dark_level = float(np.median(outside_samples))
    bright_level = float(np.median(inside_samples))
    if bright_level - dark_level < config.min_refinement_contrast:
        return BoundaryPoint(point=rough_point, status="fallback_rough")

    threshold = dark_level + 0.5 * (bright_level - dark_level)
    for (previous_offset, previous_value), (current_offset, current_value) in zip(
        profile, profile[1:], strict=False
    ):
        if previous_value <= threshold <= current_value:
            return BoundaryPoint(
                point=_crossing_point(
                    rough_point=rough_point,
                    inside_direction=inside_direction,
                    previous_offset=previous_offset,
                    previous_value=previous_value,
                    current_offset=current_offset,
                    current_value=current_value,
                    threshold=threshold,
                ),
                status="refined",
            )

    return BoundaryPoint(point=rough_point, status="fallback_rough")


def _crossing_point(
    rough_point: Point,
    inside_direction: tuple[int, int],
    previous_offset: int,
    previous_value: float,
    current_offset: int,
    current_value: float,
    threshold: float,
) -> Point:
    if current_value == previous_value:
        crossing_offset = previous_offset
    else:
        fraction = (threshold - previous_value) / (current_value - previous_value)
        crossing_offset = previous_offset + fraction * (
            current_offset - previous_offset
        )

    inside_dx, inside_dy = inside_direction
    return Point(
        x=rough_point.x + round(crossing_offset * inside_dx),
        y=rough_point.y + round(crossing_offset * inside_dy),
    )


def _sample_boundary_profile(
    image: np.ndarray,
    rough_point: Point,
    inside_direction: tuple[int, int],
    analysis_region: RectRoi,
    analysis_mask: np.ndarray,
    config: MeasurementConfig,
) -> list[tuple[int, float]]:
    profile: list[tuple[int, float]] = []
    step = config.refinement_sampling_step_px
    half_length = config.boundary_profile_half_length_px
    for offset in range(-half_length, half_length + 1, step):
        sample = _profile_sample_median(
            image=image,
            rough_point=rough_point,
            inside_direction=inside_direction,
            normal_offset=offset,
            analysis_region=analysis_region,
            analysis_mask=analysis_mask,
            averaging_width=config.boundary_profile_averaging_width_px,
        )
        if sample is not None:
            profile.append((offset, sample))
    return profile


def _profile_sample_median(
    image: np.ndarray,
    rough_point: Point,
    inside_direction: tuple[int, int],
    normal_offset: int,
    analysis_region: RectRoi,
    analysis_mask: np.ndarray,
    averaging_width: int,
) -> float | None:
    inside_dx, inside_dy = inside_direction
    tangent_dx, tangent_dy = -inside_dy, inside_dx
    half_width = averaging_width // 2
    values: list[float] = []
    for tangent_offset in range(-half_width, half_width + 1):
        x = (
            rough_point.x
            + normal_offset * inside_dx
            + tangent_offset * tangent_dx
        )
        y = (
            rough_point.y
            + normal_offset * inside_dy
            + tangent_offset * tangent_dy
        )
        if _point_inside_analysis_region(x, y, analysis_region, analysis_mask):
            values.append(float(image[y, x]))

    if not values:
        return None
    return float(np.median(values))


def _point_inside_analysis_region(
    x: int, y: int, analysis_region: RectRoi, analysis_mask: np.ndarray
) -> bool:
    if not (
        analysis_region.x <= x < analysis_region.x + analysis_region.width
        and analysis_region.y <= y < analysis_region.y + analysis_region.height
    ):
        return False
    return bool(analysis_mask[y - analysis_region.y, x - analysis_region.x])


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
    bottom_row_count = max(1, ceil(height * 0.05))

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
