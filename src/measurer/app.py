from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from measurer.export import export_measured_batch
from measurer.image_queue import AddImagesSummary, ImageQueue, RectRoi
from measurer.measurement import Measurement, MeasurementResult, measure_image


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
class BoxPlotPoint:
    group: str
    measurement_type: str
    value: float
    unit: str


class ImageCanvas(QLabel):
    def __init__(self, roi_callback) -> None:
        super().__init__("Original")
        self._roi_callback = roi_callback
        self._drag_start: QPoint | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap() is not None:
            self._drag_start = event.position().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is None or event.button() != Qt.MouseButton.LeftButton:
            return

        drag_end = event.position().toPoint()
        left = min(self._drag_start.x(), drag_end.x())
        top = min(self._drag_start.y(), drag_end.y())
        width = abs(drag_end.x() - self._drag_start.x())
        height = abs(drag_end.y() - self._drag_start.y())
        self._drag_start = None
        if width > 0 and height > 0:
            self._roi_callback(left, top, width, height)


class MeasurerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Measurer")
        self.queue = ImageQueue()

        self.add_images_button = QPushButton("Add Images")
        self.add_images_button.clicked.connect(self._choose_images)
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("Group")
        self.set_group_button = QPushButton("Set Group")
        self.set_group_button.clicked.connect(self._apply_group_to_selection)
        self.scale_input = QLineEdit()
        self.scale_input.setPlaceholderText("nm / pixel")
        self.scale_input.editingFinished.connect(self._apply_scale_to_selected_image)
        self.scale_error_label = QLabel("")
        self.clear_roi_button = QPushButton("Clear ROI")
        self.clear_roi_button.clicked.connect(self._clear_selected_roi)
        self.measure_current_button = QPushButton("Measure Current")
        self.measure_current_button.clicked.connect(self._measure_selected_image)
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._export_measured_images)
        self.original_view_button = QPushButton("Original")
        self.original_view_button.clicked.connect(self._show_original_view)
        self.result_view_button = QPushButton("Result")
        self.result_view_button.clicked.connect(self._show_result_view)
        self.box_plot_view_button = QPushButton("Box Plot")
        self.box_plot_view_button.clicked.connect(self._show_box_plot_view)
        self.debug_view_button = QPushButton("Debug")
        self.debug_view_button.clicked.connect(self._show_debug_view)
        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(
            ["Select", "File", "Group", "ROI", "Measure", "Export"]
        )
        self.file_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.file_table.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.file_table.currentCellChanged.connect(self._select_image)
        self.status_label = QLabel("No images added.")
        self.result_values_label = QLabel("")
        self.image_label = ImageCanvas(self.set_selected_roi)
        self.current_view_mode = "Original View"

        controls = QVBoxLayout()
        controls.addWidget(self.add_images_button)
        controls.addWidget(self.group_input)
        controls.addWidget(self.set_group_button)
        controls.addWidget(self.scale_input)
        controls.addWidget(self.scale_error_label)
        controls.addWidget(self.clear_roi_button)
        controls.addWidget(self.measure_current_button)
        controls.addWidget(self.export_button)
        controls.addWidget(self.file_table)
        controls.addWidget(self.status_label)

        view_controls = QHBoxLayout()
        view_controls.addWidget(self.original_view_button)
        view_controls.addWidget(self.result_view_button)
        view_controls.addWidget(self.box_plot_view_button)
        view_controls.addWidget(self.debug_view_button)

        workspace = QVBoxLayout()
        workspace.addLayout(view_controls)
        workspace.addWidget(self.image_label)
        workspace.addWidget(self.result_values_label)

        root_layout = QHBoxLayout()
        root_layout.addLayout(controls, 1)
        root_layout.addLayout(workspace, 3)

        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

    def add_image_paths(self, paths: list[str | Path]) -> AddImagesSummary:
        summary = self.queue.add_images(paths)
        self._refresh_file_table()
        self.status_label.setText(summary.message)
        if self.queue.rows:
            if self.file_table.currentRow() < 0:
                self.file_table.setCurrentCell(0, 1)
            self._select_image(self.file_table.currentRow())
        return summary

    def _select_image(
        self,
        current_row: int,
        _current_column: int = 0,
        _previous_row: int = 0,
        _previous_column: int = 0,
    ) -> None:
        if current_row < 0 or current_row >= len(self.queue.rows):
            return
        self.image_label.setPixmap(_array_to_pixmap(self.queue.rows[current_row].image))
        self.current_view_mode = "Original View"
        self.result_values_label.setText("")
        self._sync_scale_input(current_row)

    def set_selected_roi(self, x: int, y: int, width: int, height: int) -> bool:
        row_index = self.file_table.currentRow()
        if row_index < 0:
            return False

        updated = self.queue.set_roi(
            row_index, RectRoi(x=x, y=y, width=width, height=height)
        )
        if updated:
            self._refresh_file_table()
            self.file_table.setCurrentCell(row_index, 1)
            self._select_image(row_index)
        return updated

    def _choose_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Images",
            "",
            "TIFF Images (*.tif *.tiff)",
        )
        if paths:
            self.add_image_paths(paths)

    def _apply_group_to_selection(self) -> None:
        row_indexes = self._selected_row_indexes()
        if not row_indexes and self.file_table.currentRow() >= 0:
            row_indexes = [self.file_table.currentRow()]

        if self.queue.set_group(row_indexes, self.group_input.text()):
            current_row = self.file_table.currentRow()
            self._refresh_file_table()
            if current_row >= 0:
                self.file_table.setCurrentCell(current_row, 1)
            self.status_label.setText("Group updated.")
            if self.current_view_mode == "Box Plot":
                self._show_box_plot_view()
        else:
            self.status_label.setText("Group name cannot be empty.")

    def _apply_scale_to_selected_image(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0:
            return

        if self.queue.set_manual_scale(row_index, self.scale_input.text()):
            self.scale_error_label.setText("")
        else:
            self.scale_error_label.setText(self.queue.rows[row_index].scale_error)
        self._sync_scale_input(row_index)
        if self.current_view_mode == "Result View":
            self._show_result_view()
        elif self.current_view_mode == "Box Plot":
            self._show_box_plot_view()

    def _clear_selected_roi(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0:
            return

        if self.queue.clear_roi(row_index):
            self._refresh_file_table()
            self.file_table.setCurrentCell(row_index, 1)
            self._select_image(row_index)

    def _measure_selected_image(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            return

        row = self.queue.rows[row_index]
        result = measure_image(row.image, row.roi)
        if result.status != "success":
            self.queue.record_measurement_failure(row_index, result)
            self._refresh_file_table()
            self.file_table.setCurrentCell(row_index, 1)
            self.status_label.setText(result.failure_reason or "Measurement failed.")
            return

        self.queue.record_measurement_result(row_index, result)
        self._refresh_file_table()
        self.file_table.setCurrentCell(row_index, 1)
        scale = self.queue.resolve_scale(row_index)
        self.image_label.setPixmap(_result_to_pixmap(row.image, result, scale.nm_per_px))
        self.result_values_label.setText(_format_result_values(result, scale.nm_per_px))
        self.current_view_mode = "Result View"
        self.status_label.setText("Measurement completed.")

    def _export_measured_images(self) -> None:
        result = export_measured_batch(self.queue)
        self._refresh_file_table()
        self.status_label.setText(result.message)

    def _show_original_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            return

        self.image_label.setPixmap(_array_to_pixmap(self.queue.rows[row_index].image))
        self.result_values_label.setText("")
        self.current_view_mode = "Original View"

    def _show_result_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            return

        row = self.queue.rows[row_index]
        if not isinstance(row.measurement_results, MeasurementResult):
            return

        scale = self.queue.resolve_scale(row_index)
        self.image_label.setPixmap(
            _result_to_pixmap(row.image, row.measurement_results, scale.nm_per_px)
        )
        self.result_values_label.setText(
            _format_result_values(row.measurement_results, scale.nm_per_px)
        )
        self.current_view_mode = "Result View"

    def _show_box_plot_view(self) -> None:
        points, warning = _box_plot_points(self.queue)
        self.image_label.setPixmap(_box_plot_to_pixmap(points, warning))
        self.result_values_label.setText(_format_box_plot_summary(points, warning))
        self.current_view_mode = "Box Plot"

    def _show_debug_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            return

        row = self.queue.rows[row_index]
        if not isinstance(row.measurement_debug, MeasurementResult):
            return

        self.image_label.setPixmap(_debug_to_pixmap(row.image, row.measurement_debug))
        self.result_values_label.setText(_format_debug_values(row.measurement_debug))
        self.current_view_mode = "Debug View"

    def _refresh_file_table(self) -> None:
        self.file_table.setRowCount(len(self.queue.rows))
        for row_index, row in enumerate(self.queue.rows):
            values = [
                "",
                row.file_name,
                row.group,
                row.roi_status,
                row.measure_status,
                row.export_status,
            ]
            for column_index, value in enumerate(values):
                self.file_table.setItem(
                    row_index, column_index, QTableWidgetItem(value)
                )

    def _selected_row_indexes(self) -> list[int]:
        selection_model = self.file_table.selectionModel()
        if selection_model is None:
            return []
        return sorted(index.row() for index in selection_model.selectedRows())

    def _sync_scale_input(self, row_index: int) -> None:
        row = self.queue.rows[row_index]
        scale = self.queue.resolve_scale(row_index)
        with QSignalBlocker(self.scale_input):
            if scale.nm_per_px is None:
                self.scale_input.setText("")
            else:
                self.scale_input.setText(f"{scale.nm_per_px:g}")
        self.scale_input.setEnabled(row.metadata_nm_per_px is None)
        self.scale_error_label.setText(row.scale_error)


def create_window() -> MeasurerWindow:
    return MeasurerWindow()


def _array_to_pixmap(image: np.ndarray) -> QPixmap:
    display = _normalize_to_uint8(image)
    height, width = display.shape
    bytes_per_line = display.strides[0]
    qimage = QImage(
        display.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8
    ).copy()
    return QPixmap.fromImage(qimage)


def _result_to_pixmap(
    image: np.ndarray, result: MeasurementResult, nm_per_px: float | None
) -> QPixmap:
    display = _normalize_to_uint8(image)
    height, width = display.shape
    rgb = np.ascontiguousarray(np.dstack([display, display, display]))
    qimage = QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format.Format_RGB888,
    ).copy()
    painter = QPainter(qimage)
    unit = "px" if nm_per_px is None else "nm"
    scale = 1.0 if nm_per_px is None else nm_per_px
    placed_label_rects: list[QRect] = []
    for measurement in result.measurements.values():
        if measurement.status != "success":
            continue
        measurement_type = _measurement_type(measurement)
        if measurement_type is None:
            continue
        color = MEASUREMENT_COLORS[measurement_type]
        painter.setPen(QPen(color, 2))
        painter.drawLine(
            measurement.line.start.x,
            measurement.line.start.y,
            measurement.line.end.x,
            measurement.line.end.y,
        )
        label = f"{measurement.value_px * scale:.1f} {unit}"
        label_rect = _result_label_rect(
            painter=painter,
            text=label,
            center_x=round((measurement.line.start.x + measurement.line.end.x) / 2),
            center_y=round((measurement.line.start.y + measurement.line.end.y) / 2),
            image_width=width,
            image_height=height,
            placed_rects=placed_label_rects,
        )
        placed_label_rects.append(label_rect)
        _draw_outlined_text(painter, label_rect, label)
    painter.end()
    return QPixmap.fromImage(qimage)


def _result_label_rect(
    painter: QPainter,
    text: str,
    center_x: int,
    center_y: int,
    image_width: int,
    image_height: int,
    placed_rects: list[QRect],
) -> QRect:
    metrics = painter.fontMetrics()
    text_rect = metrics.boundingRect(text)
    label_width = text_rect.width() + 8
    label_height = text_rect.height() + 4
    offsets = [0, -14, 14, -28, 28, -42, 42]
    fallback_rect = QRect(0, 0, label_width, label_height)
    for offset_y in offsets:
        candidate = _clamped_label_rect(
            center_x=center_x,
            center_y=center_y + offset_y,
            label_width=label_width,
            label_height=label_height,
            image_width=image_width,
            image_height=image_height,
        )
        fallback_rect = candidate
        if not any(candidate.intersects(placed) for placed in placed_rects):
            return candidate
    return fallback_rect


def _clamped_label_rect(
    center_x: int,
    center_y: int,
    label_width: int,
    label_height: int,
    image_width: int,
    image_height: int,
) -> QRect:
    left = min(max(0, center_x - label_width // 2), max(0, image_width - label_width))
    top = min(max(0, center_y - label_height // 2), max(0, image_height - label_height))
    return QRect(left, top, label_width, label_height)


def _draw_outlined_text(painter: QPainter, label_rect: QRect, text: str) -> None:
    metrics = painter.fontMetrics()
    text_bounds = metrics.boundingRect(text)
    baseline_x = label_rect.left() + 4
    baseline_y = label_rect.top() + 2 - text_bounds.y()
    painter.setPen(QPen(QColor(5, 7, 10), 2))
    for dx, dy in [
        (-1, -1),
        (0, -1),
        (1, -1),
        (-1, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
    ]:
        painter.drawText(baseline_x + dx, baseline_y + dy, text)
    painter.setPen(QPen(QColor(245, 248, 252), 1))
    painter.drawText(baseline_x, baseline_y, text)


def _debug_to_pixmap(image: np.ndarray, result: MeasurementResult) -> QPixmap:
    display = _normalize_to_uint8(image)
    height, width = display.shape
    rgb = np.ascontiguousarray(np.dstack([display, display, display]))
    if result.detection is not None:
        region = result.analysis_region
        rough_mask = result.detection.rough_mask
        region_rgb = rgb[
            region.y : region.y + region.height,
            region.x : region.x + region.width,
        ]
        region_rgb[rough_mask] = (
            region_rgb[rough_mask].astype(np.uint16) // 2
            + np.asarray([24, 96, 180], dtype=np.uint16)
        ).astype(np.uint8)

    qimage = QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format.Format_RGB888,
    ).copy()
    painter = QPainter(qimage)
    if result.detection is not None:
        _draw_component_boxes(
            painter,
            result.analysis_region,
            result.detection.kept_candidates,
            QColor(80, 220, 120),
        )
        _draw_component_boxes(
            painter,
            result.analysis_region,
            result.detection.excluded_small_components,
            QColor(255, 190, 64),
        )
        _draw_component_boxes(
            painter,
            result.analysis_region,
            result.detection.excluded_boundary_touch_components,
            QColor(255, 80, 80),
        )
    _draw_boundary_points(painter, result)
    painter.end()
    return QPixmap.fromImage(qimage)


def _draw_boundary_points(painter: QPainter, result: MeasurementResult) -> None:
    boundaries = (
        [metal.refined_boundary for metal in result.metal_islands]
        if result.metal_islands
        else [result.refined_boundary]
    )
    for boundary in boundaries:
        for point, status in zip(
            boundary.points,
            boundary.point_statuses,
            strict=False,
        ):
            if status == "fallback_rough":
                painter.setPen(QPen(QColor(255, 96, 220), 2))
            else:
                painter.setPen(QPen(QColor(120, 240, 255), 2))
            painter.drawEllipse(point.x - 1, point.y - 1, 3, 3)


def _draw_component_boxes(
    painter, analysis_region: RectRoi, components, color: QColor
) -> None:
    painter.setPen(QPen(color, 2))
    for component in components:
        min_x, min_y, max_x, max_y = component.bbox
        painter.drawRect(
            analysis_region.x + min_x,
            analysis_region.y + min_y,
            max_x - min_x + 1,
            max_y - min_y + 1,
        )


def _format_result_values(
    result: MeasurementResult, nm_per_px: float | None
) -> str:
    unit = "px" if nm_per_px is None else "nm"
    scale = 1.0 if nm_per_px is None else nm_per_px
    return " | ".join(
        f"{name} {measurement.value_px * scale:.1f} {unit}"
        for name, measurement in result.measurements.items()
        if measurement.status == "success"
    )


def _box_plot_points(queue: ImageQueue) -> tuple[list[BoxPlotPoint], str]:
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
        units.add(unit)
        for measurement in row.measurement_results.measurements.values():
            if measurement.status != "success":
                continue
            measurement_type = _measurement_type(measurement)
            if measurement_type is None:
                continue
            points.append(
                BoxPlotPoint(
                    group=row.group,
                    measurement_type=measurement_type,
                    value=measurement.value_px * scale,
                    unit=unit,
                )
            )

    if len(units) > 1:
        return points, "Box Plot cannot mix nm and px measurements."
    return points, ""


def _measurement_type(measurement: Measurement) -> str | None:
    for measurement_type in sorted(MEASUREMENT_TYPE_ORDER, key=len, reverse=True):
        if measurement.name.endswith(measurement_type):
            return measurement_type
    return None


def _format_box_plot_summary(points: list[BoxPlotPoint], warning: str) -> str:
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


def _box_plot_to_pixmap(points: list[BoxPlotPoint], warning: str) -> QPixmap:
    width = 720
    height = 420
    qimage = QImage(width, height, QImage.Format.Format_RGB888)
    qimage.fill(QColor(18, 22, 28))
    painter = QPainter(qimage)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if warning or not points:
        painter.setPen(QPen(QColor(230, 235, 242), 1))
        painter.drawText(32, 48, warning or "Box Plot: no measured data.")
        painter.end()
        return QPixmap.fromImage(qimage)

    left = 56
    top = 40
    right = width - 32
    bottom = height - 72
    values = [point.value for point in points]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1

    painter.setPen(QPen(QColor(94, 104, 118), 1))
    painter.drawLine(left, bottom, right, bottom)
    painter.drawLine(left, top, left, bottom)

    buckets = _box_plot_buckets(points)
    bucket_count = len(buckets)
    bucket_width = (right - left) / max(1, bucket_count)
    for bucket_index, ((group, measurement_type), bucket_values) in enumerate(buckets):
        center_x = round(left + bucket_width * (bucket_index + 0.5))
        color = MEASUREMENT_COLORS[measurement_type]
        sorted_values = sorted(bucket_values)
        low = sorted_values[0]
        high = sorted_values[-1]
        q1 = _percentile(sorted_values, 25)
        median = _percentile(sorted_values, 50)
        q3 = _percentile(sorted_values, 75)
        low_y = _box_plot_y(low, min_value, max_value, top, bottom)
        high_y = _box_plot_y(high, min_value, max_value, top, bottom)
        q1_y = _box_plot_y(q1, min_value, max_value, top, bottom)
        median_y = _box_plot_y(median, min_value, max_value, top, bottom)
        q3_y = _box_plot_y(q3, min_value, max_value, top, bottom)

        painter.setPen(QPen(color, 2))
        painter.drawLine(center_x, high_y, center_x, low_y)
        painter.drawRect(center_x - 14, q3_y, 28, max(2, q1_y - q3_y))
        painter.drawLine(center_x - 16, median_y, center_x + 16, median_y)
        for point_index, value in enumerate(bucket_values):
            jitter = ((point_index % 5) - 2) * 4
            y = _box_plot_y(value, min_value, max_value, top, bottom)
            painter.drawEllipse(center_x + jitter - 2, y - 2, 4, 4)

        painter.setPen(QPen(QColor(220, 226, 235), 1))
        painter.drawText(center_x - 36, bottom + 20, group[:12])
        painter.drawText(center_x - 36, bottom + 38, measurement_type[:16])

    painter.setPen(QPen(QColor(220, 226, 235), 1))
    painter.drawText(left, 24, f"Box Plot ({points[0].unit})")
    painter.drawText(left, bottom + 58, f"{min_value:.1f} to {max_value:.1f}")
    painter.end()
    return QPixmap.fromImage(qimage)


def _box_plot_buckets(
    points: list[BoxPlotPoint],
) -> list[tuple[tuple[str, str], list[float]]]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for point in points:
        grouped.setdefault((point.group, point.measurement_type), []).append(point.value)
    return sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            MEASUREMENT_TYPE_ORDER.index(item[0][1]),
        ),
    )


def _box_plot_y(
    value: float, min_value: float, max_value: float, top: int, bottom: int
) -> int:
    fraction = (value - min_value) / (max_value - min_value)
    return round(bottom - fraction * (bottom - top))


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile / 100
    lower = int(np.floor(position))
    upper = int(np.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _format_debug_values(result: MeasurementResult) -> str:
    if result.detection is None:
        return ""

    boundaries = (
        [metal.refined_boundary for metal in result.metal_islands]
        if result.metal_islands
        else [result.refined_boundary]
    )
    refined_point_count = sum(
        boundary.refined_point_count for boundary in boundaries
    )
    fallback_point_count = sum(
        boundary.fallback_point_count for boundary in boundaries
    )
    boundary_point_count = refined_point_count + fallback_point_count
    fallback_ratio = (
        0.0 if boundary_point_count == 0 else fallback_point_count / boundary_point_count
    )

    return " | ".join(
        [
            f"Kept candidates: {len(result.detection.kept_candidates)}",
            (
                "Excluded small components: "
                f"{len(result.detection.excluded_small_components)}"
            ),
            (
                "Excluded boundary-touch components: "
                f"{len(result.detection.excluded_boundary_touch_components)}"
            ),
            f"Rejected Space pairs: {len(result.rejected_space_pairs)}",
            f"Refined points: {refined_point_count}",
            f"Fallback points: {fallback_point_count}",
            f"Fallback ratio: {fallback_ratio * 100:.1f}%",
        ]
    )


def _normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return np.ascontiguousarray(image)
    max_value = float(np.max(image))
    if max_value <= 0:
        return np.zeros(image.shape, dtype=np.uint8)
    scaled = np.asarray(image, dtype=np.float32) / max_value * 255
    return np.ascontiguousarray(np.rint(scaled).astype(np.uint8))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = create_window()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
