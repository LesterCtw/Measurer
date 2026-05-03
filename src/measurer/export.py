from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev

import numpy as np
from openpyxl import Workbook
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from measurer.image_queue import ImageQueue
from measurer.measurement import Measurement, MeasurementResult


NO_MEASURED_IMAGES_MESSAGE = "No measured images to export."
MULTI_SOURCE_OUTPUT_FOLDER_MESSAGE = "Choose an output folder for multi-source export."
OVERWRITE_CONFIRMATION_MESSAGE = "Confirm overwrite to export."
_QAPPLICATION: QApplication | None = None

MEASUREMENT_TYPE_ORDER = [
    "TCD",
    "BCD",
    "Height",
    "Horizontal Space",
    "Vertical Space",
]

MEASUREMENT_COLORS = {
    "TCD": QColor(64, 196, 255),
    "BCD": QColor(255, 183, 77),
    "Height": QColor(255, 210, 64),
    "Horizontal Space": QColor(186, 104, 200),
    "Vertical Space": QColor(129, 199, 132),
}


@dataclass(frozen=True)
class OverwriteSummary:
    output_folder: Path
    result_image_count: int = 0
    debug_image_count: int = 0
    workbook_count: int = 0

    @property
    def has_existing_targets(self) -> bool:
        return (
            self.result_image_count > 0
            or self.debug_image_count > 0
            or self.workbook_count > 0
        )


@dataclass(frozen=True)
class ExportResult:
    exported_count: int
    skipped_pending_count: int = 0
    skipped_failed_count: int = 0
    output_folder: Path | None = None
    blocked_reason: str = ""
    message: str = ""
    needs_output_folder: bool = False
    overwrite_required: bool = False
    overwrite_summary: OverwriteSummary | None = None


def export_measured_batch(
    queue: ImageQueue,
    output_folder: Path | None = None,
    overwrite_existing: bool = False,
) -> ExportResult:
    measured_rows = [
        (row_index, row)
        for row_index, row in enumerate(queue.rows)
        if row.measure_status == "Measured"
        and isinstance(row.measurement_results, MeasurementResult)
    ]
    if not measured_rows:
        return ExportResult(
            exported_count=0,
            blocked_reason=NO_MEASURED_IMAGES_MESSAGE,
            message=NO_MEASURED_IMAGES_MESSAGE,
        )

    source_folders = {row.path.parent for _, row in measured_rows}
    if output_folder is None and len(source_folders) != 1:
        return ExportResult(
            exported_count=0,
            blocked_reason=MULTI_SOURCE_OUTPUT_FOLDER_MESSAGE,
            message=MULTI_SOURCE_OUTPUT_FOLDER_MESSAGE,
            needs_output_folder=True,
        )

    if output_folder is None:
        output_folder = next(iter(source_folders))

    measured_folder = output_folder / "measured_image"
    debug_folder = output_folder / "debug_image"
    planned_rows = [
        (
            row_index,
            row,
            measured_folder / f"{row.path.stem}_result.png",
            debug_folder / f"{row.path.stem}_debug.png",
        )
        for row_index, row in measured_rows
    ]
    workbook_path = measured_folder / "measurements.xlsx"
    overwrite_summary = _existing_target_summary(
        output_folder=output_folder,
        result_paths=[result_path for _, _, result_path, _ in planned_rows],
        debug_paths=[debug_path for _, _, _, debug_path in planned_rows],
        workbook_path=workbook_path,
    )
    if overwrite_summary.has_existing_targets and not overwrite_existing:
        return ExportResult(
            exported_count=0,
            output_folder=output_folder,
            blocked_reason=OVERWRITE_CONFIRMATION_MESSAGE,
            message=OVERWRITE_CONFIRMATION_MESSAGE,
            overwrite_required=True,
            overwrite_summary=overwrite_summary,
        )

    measured_folder.mkdir(parents=True, exist_ok=True)
    debug_folder.mkdir(parents=True, exist_ok=True)

    for row_index, row, result_path, debug_path in planned_rows:
        scale = queue.resolve_scale(row_index)
        result = row.measurement_results
        _save_result_image(
            row.image,
            result,
            scale.nm_per_px,
            result_path,
        )
        _save_debug_image(row.image, result, debug_path)

    _write_workbook(queue, workbook_path)
    queue.record_export_success([row_index for row_index, _ in measured_rows])

    skipped_pending_count = sum(
        1 for row in queue.rows if row.measure_status == "Pending"
    )
    skipped_failed_count = sum(1 for row in queue.rows if row.measure_status == "Failed")
    exported_count = len(measured_rows)
    return ExportResult(
        exported_count=exported_count,
        skipped_pending_count=skipped_pending_count,
        skipped_failed_count=skipped_failed_count,
        output_folder=output_folder,
        message=_format_export_message(
            exported_count, skipped_pending_count, skipped_failed_count
        ),
    )


def _existing_target_summary(
    output_folder: Path,
    result_paths: list[Path],
    debug_paths: list[Path],
    workbook_path: Path,
) -> OverwriteSummary:
    return OverwriteSummary(
        output_folder=output_folder,
        result_image_count=sum(1 for path in set(result_paths) if path.exists()),
        debug_image_count=sum(1 for path in set(debug_paths) if path.exists()),
        workbook_count=1 if workbook_path.exists() else 0,
    )


def _save_result_image(
    image: np.ndarray,
    result: MeasurementResult,
    nm_per_px: float | None,
    output_path: Path,
) -> None:
    _ensure_qapplication()
    qimage = _rgb_qimage(image)
    painter = QPainter(qimage)
    _draw_measurement_lines(painter, result, nm_per_px)
    painter.end()
    qimage.save(str(output_path))


def _save_debug_image(
    image: np.ndarray, result: MeasurementResult, output_path: Path
) -> None:
    _ensure_qapplication()
    original = _rgb_qimage(image)
    width = original.width()
    height = original.height()
    debug_image = QImage(width * 2, height * 2, QImage.Format.Format_RGB888)
    debug_image.fill(QColor(18, 22, 28))
    painter = QPainter(debug_image)
    painter.drawImage(0, 0, original)
    painter.drawImage(width, 0, _rough_mask_qimage(image, result))
    painter.drawImage(0, height, _component_qimage(image, result))
    result_panel = _rgb_qimage(image)
    result_painter = QPainter(result_panel)
    _draw_measurement_lines(result_painter, result, nm_per_px=None)
    result_painter.end()
    painter.drawImage(width, height, result_panel)
    painter.end()
    debug_image.save(str(output_path))


def _write_workbook(queue: ImageQueue, output_path: Path) -> None:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    measurements_sheet = workbook.create_sheet("Measurements")
    trace_sheet = workbook.create_sheet("Trace")

    summary_sheet.append(
        [
            "group",
            "measurement type",
            "count",
            "mean",
            "median",
            "min",
            "max",
            "std",
            "unit",
        ]
    )
    measurements_sheet.append(
        ["file", "group", "measurement type", "target ID", "status", "value", "unit"]
    )
    trace_sheet.append(
        [
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
            "refined_point_count",
            "fallback_point_count",
            "fallback_ratio",
        ]
    )

    summary_values: dict[tuple[str, str, str], list[float]] = {}
    for row_index, row in enumerate(queue.rows):
        if row.measure_status != "Measured":
            continue
        if not isinstance(row.measurement_results, MeasurementResult):
            continue

        result = row.measurement_results
        scale_resolution = queue.resolve_scale(row_index)
        unit = "px" if scale_resolution.nm_per_px is None else "nm"
        scale = 1.0 if scale_resolution.nm_per_px is None else scale_resolution.nm_per_px
        for measurement in result.measurements.values():
            measurement_type = _measurement_type(measurement)
            if measurement_type is None:
                continue
            target_id = _target_id(measurement, measurement_type)
            value = (
                None
                if measurement.status != "success"
                else round(measurement.value_px * scale, 1)
            )
            measurements_sheet.append(
                [
                    row.file_name,
                    row.group,
                    measurement_type,
                    target_id,
                    measurement.status,
                    value,
                    unit,
                ]
            )
            if measurement.status == "success" and value is not None:
                summary_values.setdefault((row.group, measurement_type, unit), []).append(
                    value
                )
            trace_sheet.append(
                _trace_row(
                    file_name=row.file_name,
                    group=row.group,
                    measurement=measurement,
                    measurement_type=measurement_type,
                    target_id=target_id,
                    result=result,
                    scale_source=scale_resolution.source,
                    scale_nm_per_px=scale_resolution.nm_per_px,
                    roi_type="rectangle" if row.roi is not None else "full_image",
                )
            )

    for (group, measurement_type, unit), values in sorted(
        summary_values.items(),
        key=lambda item: (
            item[0][0],
            MEASUREMENT_TYPE_ORDER.index(item[0][1]),
            item[0][2],
        ),
    ):
        summary_sheet.append(
            [
                group,
                measurement_type,
                len(values),
                round(mean(values), 1),
                round(median(values), 1),
                round(min(values), 1),
                round(max(values), 1),
                round(pstdev(values), 1),
                unit,
            ]
        )
    workbook.save(output_path)


def _trace_row(
    file_name: str,
    group: str,
    measurement: Measurement,
    measurement_type: str,
    target_id: str,
    result: MeasurementResult,
    scale_source: str,
    scale_nm_per_px: float | None,
    roi_type: str,
) -> list[object]:
    roi = result.analysis_region
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
        roi_type,
        roi.x,
        roi.y,
        roi.width,
        roi.height,
        refined_count,
        fallback_count,
        fallback_ratio,
    ]


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


def _draw_measurement_lines(
    painter: QPainter, result: MeasurementResult, nm_per_px: float | None
) -> None:
    unit = "px" if nm_per_px is None else "nm"
    scale = 1.0 if nm_per_px is None else nm_per_px
    for measurement in result.measurements.values():
        if measurement.status != "success":
            continue
        measurement_type = _measurement_type(measurement)
        if measurement_type is None:
            continue
        painter.setPen(QPen(MEASUREMENT_COLORS[measurement_type], 2))
        painter.drawLine(
            measurement.line.start.x,
            measurement.line.start.y,
            measurement.line.end.x,
            measurement.line.end.y,
        )
        painter.setPen(QPen(QColor(245, 248, 252), 1))
        painter.drawText(
            round((measurement.line.start.x + measurement.line.end.x) / 2),
            round((measurement.line.start.y + measurement.line.end.y) / 2),
            f"{measurement.value_px * scale:.1f} {unit}",
        )


def _rough_mask_qimage(image: np.ndarray, result: MeasurementResult) -> QImage:
    qimage = _rgb_qimage(image)
    if result.detection is None:
        return qimage

    region = result.analysis_region
    painter = QPainter(qimage)
    painter.setPen(QPen(QColor(24, 96, 180), 1))
    mask = result.detection.rough_mask
    ys, xs = np.where(mask)
    for x, y in zip(xs, ys, strict=False):
        painter.drawPoint(region.x + int(x), region.y + int(y))
    painter.end()
    return qimage


def _component_qimage(image: np.ndarray, result: MeasurementResult) -> QImage:
    qimage = _rgb_qimage(image)
    if result.detection is None:
        return qimage

    painter = QPainter(qimage)
    for components, color in [
        (result.detection.kept_candidates, QColor(80, 220, 120)),
        (result.detection.excluded_small_components, QColor(255, 190, 64)),
        (result.detection.excluded_boundary_touch_components, QColor(255, 80, 80)),
    ]:
        painter.setPen(QPen(color, 2))
        for component in components:
            min_x, min_y, max_x, max_y = component.bbox
            painter.drawRect(
                result.analysis_region.x + min_x,
                result.analysis_region.y + min_y,
                max_x - min_x + 1,
                max_y - min_y + 1,
            )
    painter.end()
    return qimage


def _rgb_qimage(image: np.ndarray) -> QImage:
    display = _normalize_to_uint8(image)
    height, width = display.shape
    rgb = np.ascontiguousarray(np.dstack([display, display, display]))
    return QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format.Format_RGB888,
    ).copy()


def _normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return np.ascontiguousarray(image)
    max_value = float(np.max(image))
    if max_value <= 0:
        return np.zeros(image.shape, dtype=np.uint8)
    scaled = np.asarray(image, dtype=np.float32) / max_value * 255
    return np.ascontiguousarray(np.rint(scaled).astype(np.uint8))


def _measurement_type(measurement: Measurement) -> str | None:
    for measurement_type in sorted(MEASUREMENT_TYPE_ORDER, key=len, reverse=True):
        if measurement.name.endswith(measurement_type):
            return measurement_type
    return None


def _target_id(measurement: Measurement, measurement_type: str) -> str:
    prefix = measurement.name[: -len(measurement_type)].strip()
    return prefix or "M001"


def _format_export_message(
    exported_count: int, skipped_pending_count: int, skipped_failed_count: int
) -> str:
    image_label = "image" if exported_count == 1 else "images"
    message = f"Exported {exported_count} measured {image_label}."
    skipped_parts = []
    if skipped_pending_count:
        skipped_parts.append(f"{skipped_pending_count} pending")
    if skipped_failed_count:
        skipped_parts.append(f"{skipped_failed_count} failed")
    if skipped_parts:
        message += f" Skipped {', '.join(skipped_parts)}."
    return message


def _ensure_qapplication() -> None:
    global _QAPPLICATION
    _QAPPLICATION = QApplication.instance() or QApplication([])
