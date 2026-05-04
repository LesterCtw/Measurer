from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor

from measurer.image_queue import ImageQueue
from measurer.measurement import MeasurementResult
from measurer.measurement_report import MEASUREMENT_TYPE_ORDER, measurement_report_key


@dataclass(frozen=True)
class BoxPlotPoint:
    group: str
    measurement_type: str
    value: float
    unit: str


def box_plot_points(
    queue: ImageQueue, selected_measurement_types: set[str] | None = None
) -> tuple[list[BoxPlotPoint], str]:
    if selected_measurement_types is not None and not selected_measurement_types:
        return [], "Box Plot: no selected measurement types."

    points: list[BoxPlotPoint] = []
    units: set[str] = set()
    for row_index, row in enumerate(queue.rows):
        if row.measure_status != "Measured":
            continue
        if not isinstance(row.measurement_results, MeasurementResult):
            continue

        scale_resolution = queue.resolve_scale(row_index)
        unit = "px" if scale_resolution.nm_per_px is None else "nm"
        scale = 1.0 if scale_resolution.nm_per_px is None else scale_resolution.nm_per_px
        row_has_visible_measurement = False
        for measurement in row.measurement_results.measurements.values():
            if measurement.status != "success":
                continue
            report_key = measurement_report_key(measurement)
            if report_key is None:
                continue
            measurement_type = report_key.measurement_type
            if (
                selected_measurement_types is not None
                and measurement_type not in selected_measurement_types
            ):
                continue
            row_has_visible_measurement = True
            points.append(
                BoxPlotPoint(
                    group=row.group,
                    measurement_type=measurement_type,
                    value=measurement.value_px * scale,
                    unit=unit,
                )
            )
        if row_has_visible_measurement:
            units.add(unit)

    if len(units) > 1:
        return points, "Box Plot cannot mix nm and px measurements."
    return points, ""


def format_box_plot_summary(points: list[BoxPlotPoint], warning: str) -> str:
    if warning:
        return warning
    if not points:
        return "Box Plot: no measured data."

    groups = ", ".join(sorted({point.group for point in points}))
    types = ", ".join(
        measurement_type
        for measurement_type in MEASUREMENT_TYPE_ORDER
        if any(point.measurement_type == measurement_type for point in points)
    )
    unit = points[0].unit
    count = len(points)
    label = "measurement" if count == 1 else "measurements"
    return (
        f"Box Plot: {count} {label} | Unit: {unit} | "
        f"Groups: {groups} | Types: {types}"
    )


def box_plot_buckets(
    points: list[BoxPlotPoint],
) -> list[tuple[tuple[str, str], list[float]]]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for point in points:
        grouped.setdefault((point.group, point.measurement_type), []).append(point.value)
    return sorted(
        grouped.items(),
        key=lambda item: (
            MEASUREMENT_TYPE_ORDER.index(item[0][1]),
            item[0][0],
        ),
    )


def box_plot_label_clusters(
    buckets: list[tuple[tuple[str, str], list[float]]],
) -> list[tuple[str, int, int]]:
    clusters: list[tuple[str, int, int]] = []
    if not buckets:
        return clusters

    current_type = buckets[0][0][1]
    start_index = 0
    for index, ((_group, measurement_type), _values) in enumerate(buckets[1:], start=1):
        if measurement_type == current_type:
            continue
        clusters.append((current_type, start_index, index - 1))
        current_type = measurement_type
        start_index = index
    clusters.append((current_type, start_index, len(buckets) - 1))
    return clusters


def box_plot_y(
    value: float, min_value: float, max_value: float, top: int, bottom: int
) -> int:
    fraction = (value - min_value) / (max_value - min_value)
    return round(bottom - fraction * (bottom - top))


def box_plot_ticks(
    min_value: float, max_value: float, tick_count: int = 5
) -> list[float]:
    if tick_count <= 1:
        return [min_value]
    step = (max_value - min_value) / (tick_count - 1)
    return [min_value + step * index for index in range(tick_count)]


def percentile(sorted_values: list[float], percentile_value: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile_value / 100
    lower = floor(position)
    upper = ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
