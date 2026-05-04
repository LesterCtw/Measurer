from __future__ import annotations

from dataclasses import dataclass

from measurer.measurement import Measurement, MeasurementResult


MEASUREMENT_TYPE_ORDER = (
    "TCD",
    "BCD",
    "Height",
    "Horizontal Space",
    "Vertical Space",
)

MEASUREMENT_TYPE_COLORS = {
    "TCD": (64, 196, 255),
    "BCD": (255, 183, 77),
    "Height": (255, 210, 64),
    "Horizontal Space": (186, 104, 200),
    "Vertical Space": (129, 199, 132),
}


@dataclass(frozen=True)
class MeasurementReportKey:
    measurement_type: str
    target_id: str


@dataclass(frozen=True)
class MeasurementReportItem:
    measurement: Measurement
    measurement_type: str
    target_id: str
    display_value: float
    unit: str
    label: str
    color_rgb: tuple[int, int, int]


def successful_measurement_report_items(
    result: MeasurementResult, nm_per_px: float | None
) -> list[MeasurementReportItem]:
    unit = "px" if nm_per_px is None else "nm"
    scale = 1.0 if nm_per_px is None else nm_per_px
    items: list[MeasurementReportItem] = []
    for measurement in result.measurements.values():
        if measurement.status != "success":
            continue
        report_key = measurement_report_key(measurement)
        if report_key is None:
            continue
        display_value = measurement.value_px * scale
        items.append(
            MeasurementReportItem(
                measurement=measurement,
                measurement_type=report_key.measurement_type,
                target_id=report_key.target_id,
                display_value=display_value,
                unit=unit,
                label=f"{display_value:.1f} {unit}",
                color_rgb=MEASUREMENT_TYPE_COLORS[report_key.measurement_type],
            )
        )
    return items


def format_measurement_summary(
    result: MeasurementResult, nm_per_px: float | None
) -> str:
    values_by_type: dict[str, list[float]] = {
        measurement_type: [] for measurement_type in MEASUREMENT_TYPE_ORDER
    }
    for item in successful_measurement_report_items(result, nm_per_px):
        values_by_type[item.measurement_type].append(item.display_value)

    parts = []
    unit = "px" if nm_per_px is None else "nm"
    for measurement_type in MEASUREMENT_TYPE_ORDER:
        values = values_by_type[measurement_type]
        if not values:
            continue
        minimum = min(values)
        maximum = max(values)
        value_label = (
            f"{minimum:.1f}"
            if minimum == maximum
            else f"{minimum:.1f}-{maximum:.1f}"
        )
        parts.append(f"{measurement_type}: {value_label} {unit} (n={len(values)})")
    return " | ".join(parts)


def measurement_report_key(measurement: Measurement) -> MeasurementReportKey | None:
    measurement_type = measurement_type_from_name(measurement.name)
    if measurement_type is None:
        return None

    return MeasurementReportKey(
        measurement_type=measurement_type,
        target_id=target_id_from_name(measurement.name, measurement_type),
    )


def measurement_type_from_name(name: str) -> str | None:
    for measurement_type in sorted(MEASUREMENT_TYPE_ORDER, key=len, reverse=True):
        if name.endswith(measurement_type):
            return measurement_type
    return None


def target_id_from_name(name: str, measurement_type: str) -> str:
    prefix = name[: -len(measurement_type)].strip()
    return prefix or "M001"
