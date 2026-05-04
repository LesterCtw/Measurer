from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

from measurer.image_queue import ImageQueue
from measurer.measurement import MeasurementResult
from measurer.measurement_report import MEASUREMENT_TYPE_ORDER, measurement_report_key

_STANDARD_NORMAL = NormalDist()


@dataclass(frozen=True)
class ProbabilityPlotPoint:
    group: str
    measurement_type: str
    value: float
    unit: str


@dataclass(frozen=True)
class ProbabilityPlotBucketPoint:
    value: float
    probability_percent: float


@dataclass(frozen=True)
class ProbabilityPlotBucket:
    key: tuple[str, str]
    points: list[ProbabilityPlotBucketPoint]

    @property
    def drawable(self) -> bool:
        return len(self.points) >= 2


def probability_plot_points(
    queue: ImageQueue, selected_measurement_types: set[str] | None = None
) -> tuple[list[ProbabilityPlotPoint], str]:
    if selected_measurement_types is not None and not selected_measurement_types:
        return [], "P-Chart: no selected measurement types."

    points: list[ProbabilityPlotPoint] = []
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
                ProbabilityPlotPoint(
                    group=row.group,
                    measurement_type=measurement_type,
                    value=measurement.value_px * scale,
                    unit=unit,
                )
            )
        if row_has_visible_measurement:
            units.add(unit)

    if len(units) > 1:
        return points, "P-Chart cannot mix nm and px measurements."
    return points, ""


def format_probability_plot_summary(
    points: list[ProbabilityPlotPoint], warning: str
) -> str:
    if warning:
        return warning
    if not points:
        return "P-Chart: no measured data."

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
        f"P-Chart: {count} {label} | Unit: {unit} | "
        f"Groups: {groups} | Types: {types}"
    )


def probability_plot_buckets(
    points: list[ProbabilityPlotPoint],
) -> list[ProbabilityPlotBucket]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for point in points:
        grouped.setdefault((point.group, point.measurement_type), []).append(point.value)

    buckets = []
    for key, values in grouped.items():
        sorted_values = sorted(values)
        bucket_points = [
            ProbabilityPlotBucketPoint(
                value=value,
                probability_percent=(index + 0.5) / len(sorted_values) * 100,
            )
            for index, value in enumerate(sorted_values)
        ]
        buckets.append(ProbabilityPlotBucket(key=key, points=bucket_points))

    return sorted(
        buckets,
        key=lambda bucket: (
            MEASUREMENT_TYPE_ORDER.index(bucket.key[1]),
            bucket.key[0],
        ),
    )


def normal_probability_score(probability_percent: float) -> float:
    return _STANDARD_NORMAL.inv_cdf(probability_percent / 100)
