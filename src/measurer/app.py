from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from measurer.export import OverwriteSummary, export_measured_batch
from measurer.image_queue import AddImagesSummary, ImageQueue, RectRoi
from measurer.measurement import (
    HARD_MIN_COMPONENT_AREA_PX,
    Measurement,
    MeasurementResult,
    measure_image,
)


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


class ImageCanvas(QWidget):
    def __init__(self, roi_callback) -> None:
        super().__init__()
        self._roi_callback = roi_callback
        self._pixmap: QPixmap | None = None
        self._roi: RectRoi | None = None
        self._show_roi = False
        self._measurement_result: MeasurementResult | None = None
        self._measurement_nm_per_px: float | None = None
        self._box_plot_points: list[BoxPlotPoint] | None = None
        self._box_plot_warning = ""
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self.setObjectName("ImageCanvas")
        self.setMinimumSize(520, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def setPixmap(self, pixmap: QPixmap) -> None:  # noqa: N802
        self._pixmap = pixmap
        self._box_plot_points = None
        self._box_plot_warning = ""
        self._drag_start = None
        self._drag_current = None
        self.update()

    def pixmap(self) -> QPixmap | None:
        return self._pixmap

    def set_roi(self, roi: RectRoi | None, *, visible: bool) -> None:
        self._roi = roi
        self._show_roi = visible
        self.update()

    def set_measurement_overlay(
        self, result: MeasurementResult | None, nm_per_px: float | None
    ) -> None:
        self._measurement_result = result
        self._measurement_nm_per_px = nm_per_px
        self.update()

    def set_box_plot(self, points: list[BoxPlotPoint], warning: str) -> None:
        self._pixmap = None
        self._measurement_result = None
        self._measurement_nm_per_px = None
        self._roi = None
        self._show_roi = False
        self._box_plot_points = points
        self._box_plot_warning = warning
        self.update()

    def roi_preview(self) -> RectRoi | None:
        if self._drag_start is None or self._drag_current is None:
            return None
        return _rect_roi_from_points(self._drag_start, self._drag_current)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(720, 540)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#15171b"))

        if self._box_plot_points is not None:
            self._draw_box_plot(painter, self._box_plot_points, self._box_plot_warning)
            return

        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QPen(QColor("#7f8794"), 1))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Add images to preview and draw ROI.",
            )
            return

        image_rect = self._image_rect()
        painter.drawPixmap(image_rect, self._pixmap)

        if self._measurement_result is not None:
            self._draw_measurement_overlay(painter, self._measurement_result)

        if self._show_roi and self._roi is not None:
            self._draw_roi(painter, self._roi, QColor("#40c4ff"))

        preview = self.roi_preview()
        if preview is not None:
            self._draw_roi(painter, preview, QColor("#40c4ff"), preview=True)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None:
            return
        image_point = self._widget_to_image_point(event.position().toPoint())
        if image_point is not None:
            self._drag_start = image_point
            self._drag_current = image_point
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        image_point = self._widget_to_image_point(event.position().toPoint(), clamp=True)
        if image_point is not None:
            self._drag_current = image_point
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is None or event.button() != Qt.MouseButton.LeftButton:
            return

        image_point = self._widget_to_image_point(event.position().toPoint(), clamp=True)
        if image_point is not None:
            self._drag_current = image_point
        preview = self.roi_preview()
        self._drag_start = None
        self._drag_current = None
        self.update()
        if preview is not None and preview.width > 0 and preview.height > 0:
            self._roi_callback(preview.x, preview.y, preview.width, preview.height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().resizeEvent(event)

    def _image_rect(self) -> QRect:
        if self._pixmap is None:
            return self.rect()

        image_size = self._pixmap.size()
        image_size.scale(self.rect().size(), Qt.AspectRatioMode.KeepAspectRatio)
        top_left = QPoint(
            self.rect().left() + (self.rect().width() - image_size.width()) // 2,
            self.rect().top() + (self.rect().height() - image_size.height()) // 2,
        )
        return QRect(top_left, image_size)

    def _widget_to_image_point(
        self, point: QPoint, *, clamp: bool = False
    ) -> QPoint | None:
        if self._pixmap is None or self._pixmap.isNull():
            return None

        image_rect = self._image_rect()
        if image_rect.width() <= 0 or image_rect.height() <= 0:
            return None
        if not clamp and not image_rect.contains(point):
            return None

        clamped_x = min(max(point.x(), image_rect.left()), image_rect.right())
        clamped_y = min(max(point.y(), image_rect.top()), image_rect.bottom())
        image_x = round(
            (clamped_x - image_rect.left()) * self._pixmap.width() / image_rect.width()
        )
        image_y = round(
            (clamped_y - image_rect.top()) * self._pixmap.height() / image_rect.height()
        )
        return QPoint(
            min(max(0, image_x), self._pixmap.width()),
            min(max(0, image_y), self._pixmap.height()),
        )

    def _draw_roi(
        self,
        painter: QPainter,
        roi: RectRoi,
        color: QColor,
        *,
        preview: bool = False,
    ) -> None:
        rect = self._roi_to_widget_rect(roi)

        pen = QPen(color, 2)
        if preview:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        painter.setBrush(color)
        painter.setPen(QPen(QColor("#101114"), 1))
        handle_size = 8
        for point in [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        ]:
            painter.drawRect(
                point.x() - handle_size // 2,
                point.y() - handle_size // 2,
                handle_size,
                handle_size,
            )

        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _roi_to_widget_rect(self, roi: RectRoi) -> QRect:
        image_rect = self._image_rect()
        if self._pixmap is None or self._pixmap.isNull():
            return QRect()
        left = round(image_rect.left() + roi.x * image_rect.width() / self._pixmap.width())
        top = round(image_rect.top() + roi.y * image_rect.height() / self._pixmap.height())
        width = round(roi.width * image_rect.width() / self._pixmap.width())
        height = round(roi.height * image_rect.height() / self._pixmap.height())
        return QRect(left, top, max(1, width), max(1, height))

    def _draw_measurement_overlay(
        self, painter: QPainter, result: MeasurementResult
    ) -> None:
        unit = "px" if self._measurement_nm_per_px is None else "nm"
        scale = 1.0 if self._measurement_nm_per_px is None else self._measurement_nm_per_px
        placed_label_rects: list[QRect] = []
        for measurement in result.measurements.values():
            if measurement.status != "success":
                continue
            measurement_type = _measurement_type(measurement)
            if measurement_type is None:
                continue
            color = MEASUREMENT_COLORS[measurement_type]
            start = self._image_to_widget_point(
                measurement.line.start.x, measurement.line.start.y
            )
            end = self._image_to_widget_point(
                measurement.line.end.x, measurement.line.end.y
            )
            painter.setPen(QPen(color, 2))
            painter.drawLine(start, end)

            label = f"{measurement.value_px * scale:.1f} {unit}"
            label_rect = _result_label_rect(
                painter=painter,
                text=label,
                center_x=round((start.x() + end.x()) / 2),
                center_y=round((start.y() + end.y()) / 2),
                image_width=self.width(),
                image_height=self.height(),
                placed_rects=placed_label_rects,
            )
            placed_label_rects.append(label_rect)
            _draw_outlined_text(painter, label_rect, label)

    def _image_to_widget_point(self, x: int, y: int) -> QPoint:
        image_rect = self._image_rect()
        if self._pixmap is None or self._pixmap.isNull():
            return QPoint()
        return QPoint(
            round(image_rect.left() + x * image_rect.width() / self._pixmap.width()),
            round(image_rect.top() + y * image_rect.height() / self._pixmap.height()),
        )

    def _draw_box_plot(
        self, painter: QPainter, points: list[BoxPlotPoint], warning: str
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if warning or not points:
            painter.setPen(QPen(QColor(230, 235, 242), 1))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                warning or "Box Plot: no measured data.",
            )
            return

        left = 56
        top = 72
        right = self.width() - 28
        bottom = self.height() - 78
        if right <= left or bottom <= top:
            return

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
        metrics = painter.fontMetrics()
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
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(center_x, high_y, center_x, low_y)
            painter.drawRect(center_x - 14, q3_y, 28, max(2, q1_y - q3_y))
            painter.drawLine(center_x - 16, median_y, center_x + 16, median_y)
            painter.setBrush(color)
            for point_index, value in enumerate(bucket_values):
                jitter = ((point_index % 5) - 2) * 4
                y = _box_plot_y(value, min_value, max_value, top, bottom)
                painter.drawEllipse(center_x + jitter - 2, y - 2, 4, 4)

            painter.setPen(QPen(QColor(220, 226, 235), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            group_label = _elided_center_label(metrics, group, round(bucket_width) - 12)
            painter.drawText(
                center_x - metrics.horizontalAdvance(group_label) // 2,
                bottom + 28,
                group_label,
            )

        for measurement_type, start_index, end_index in _box_plot_label_clusters(buckets):
            cluster_left = left + bucket_width * start_index
            cluster_right = left + bucket_width * (end_index + 1)
            cluster_center_x = round((cluster_left + cluster_right) / 2)
            max_label_width = round(cluster_right - cluster_left) - 12
            type_label = _elided_center_label(metrics, measurement_type, max_label_width)
            painter.drawText(
                cluster_center_x - metrics.horizontalAdvance(type_label) // 2,
                bottom + 52,
                type_label,
            )

        painter.setPen(QPen(QColor(220, 226, 235), 1))
        painter.drawText(left, 30, f"Box Plot ({points[0].unit})")
        painter.drawText(left, 52, f"{min_value:.1f} to {max_value:.1f}")


def _rect_roi_from_points(start: QPoint, end: QPoint) -> RectRoi:
    left = min(start.x(), end.x())
    top = min(start.y(), end.y())
    width = abs(end.x() - start.x())
    height = abs(end.y() - start.y())
    return RectRoi(x=left, y=top, width=width, height=height)


class MeasurerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Measurer")
        self.resize(1280, 800)
        self.setMinimumSize(980, 620)
        self.queue = ImageQueue()

        self.add_images_button = QPushButton("Add Images")
        self.add_images_button.setObjectName("PrimaryButton")
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
        self.measure_current_button.setObjectName("PrimaryButton")
        self.measure_current_button.clicked.connect(self._measure_selected_image)
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._export_measured_images)
        self.original_view_button = QPushButton("Original")
        self.original_view_button.setCheckable(True)
        self.original_view_button.clicked.connect(self._show_original_view)
        self.result_view_button = QPushButton("Result")
        self.result_view_button.setCheckable(True)
        self.result_view_button.clicked.connect(self._show_result_view)
        self.box_plot_view_button = QPushButton("Box Plot")
        self.box_plot_view_button.setCheckable(True)
        self.box_plot_view_button.clicked.connect(self._show_box_plot_view)
        self.debug_view_button = QPushButton("Debug")
        self.debug_view_button.setCheckable(True)
        self.debug_view_button.clicked.connect(self._show_debug_view)
        self.file_table = QTableWidget(0, 6)
        self.file_table.setObjectName("FileQueue")
        self.file_table.setHorizontalHeaderLabels(
            ["", "Image", "Group", "Status", "Measure", "Export"]
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self.file_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed
        )
        self.file_table.setColumnHidden(0, True)
        self.file_table.setColumnHidden(2, True)
        self.file_table.setColumnHidden(3, True)
        self.file_table.setColumnHidden(4, True)
        self.file_table.setColumnHidden(5, True)
        self.file_table.setColumnWidth(2, 92)
        self.file_table.setColumnWidth(3, 190)
        self.file_table.verticalHeader().hide()
        self.file_table.setShowGrid(False)
        self.file_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.file_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.file_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.file_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.file_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.file_table.currentCellChanged.connect(self._select_image)
        self.status_label = QLabel("No images added.")
        self.status_label.setObjectName("StatusTitle")
        self.status_label.setWordWrap(True)
        self.result_values_label = QLabel("")
        self.result_values_label.setObjectName("ResultValues")
        self.result_values_label.setWordWrap(True)
        self.image_label = ImageCanvas(self.set_selected_roi)
        self.current_view_mode = "Original View"
        self.box_plot_type_checkboxes: dict[str, QCheckBox] = {}
        self.box_plot_select_all_checkbox = QCheckBox("All")
        self.group_controls_panel = QFrame()
        self.group_controls_panel.setObjectName("GroupControls")

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(520)
        controls = QVBoxLayout()
        controls.setContentsMargins(24, 24, 24, 24)
        controls.setSpacing(12)
        title = QLabel("Measurer")
        title.setObjectName("Title")
        controls.addWidget(title)
        controls.addWidget(self.add_images_button)
        controls.addWidget(self.scale_input)
        controls.addWidget(self.scale_error_label)
        controls.addWidget(self.clear_roi_button)
        controls.addWidget(self.measure_current_button)
        controls.addWidget(self.export_button)
        group_controls = QHBoxLayout(self.group_controls_panel)
        group_controls.setContentsMargins(0, 0, 0, 0)
        group_controls.setSpacing(8)
        group_controls.addWidget(self.group_input, 1)
        group_controls.addWidget(self.set_group_button)
        controls.addWidget(self.group_controls_panel)
        controls.addWidget(self.file_table)
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.addWidget(self.status_label)
        controls.addWidget(status_card)
        sidebar.setLayout(controls)

        view_controls = QHBoxLayout()
        view_controls.setSpacing(8)
        view_controls.addWidget(self.original_view_button)
        view_controls.addWidget(self.result_view_button)
        view_controls.addWidget(self.box_plot_view_button)
        view_controls.addWidget(self.debug_view_button)
        view_controls.addStretch(1)

        self.box_plot_filter_panel = QFrame()
        self.box_plot_filter_panel.setObjectName("BoxPlotFilters")
        box_plot_filter_layout = QHBoxLayout(self.box_plot_filter_panel)
        box_plot_filter_layout.setContentsMargins(14, 8, 14, 8)
        box_plot_filter_layout.setSpacing(18)
        box_plot_label = QLabel("Measurements")
        box_plot_label.setObjectName("BoxPlotFilterLabel")
        box_plot_filter_layout.addWidget(box_plot_label)
        self.box_plot_select_all_checkbox.setChecked(True)
        self.box_plot_select_all_checkbox.setObjectName("BoxPlotFilterCheckbox")
        self.box_plot_select_all_checkbox.toggled.connect(
            self._set_all_box_plot_measurement_types
        )
        box_plot_filter_layout.addWidget(self.box_plot_select_all_checkbox)
        for measurement_type in MEASUREMENT_TYPE_ORDER:
            checkbox = QCheckBox(measurement_type)
            checkbox.setObjectName("BoxPlotFilterCheckbox")
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._box_plot_type_filter_toggled)
            self.box_plot_type_checkboxes[measurement_type] = checkbox
            box_plot_filter_layout.addWidget(checkbox)
        box_plot_filter_layout.addStretch(1)
        self.box_plot_filter_panel.setVisible(False)

        workspace_frame = QFrame()
        workspace_frame.setObjectName("PreviewArea")
        workspace = QVBoxLayout()
        workspace.setContentsMargins(24, 24, 24, 24)
        workspace.setSpacing(12)
        workspace.addLayout(view_controls)
        workspace.addWidget(self.box_plot_filter_panel)
        workspace.addWidget(self.image_label)
        workspace.addWidget(self.result_values_label)
        workspace_frame.setLayout(workspace)

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(workspace_frame, 1)

        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)
        self.setStyleSheet(_stylesheet())
        self._sync_view_buttons()

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
        row = self.queue.rows[current_row]
        self._sync_scale_input(current_row)
        if isinstance(row.measurement_results, MeasurementResult):
            self._show_result_view()
            return

        self.image_label.setPixmap(_array_to_pixmap(row.image))
        self.image_label.set_measurement_overlay(None, None)
        self.image_label.set_roi(row.roi, visible=True)
        self.current_view_mode = "Original View"
        self.result_values_label.setText("")
        self._sync_view_buttons()

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
            "STEM ZC Images (*.tif *.tiff *.dm3)",
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
        if _roi_is_too_small(row.roi):
            self.status_label.setText("ROI is too small.")
            return

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
        self.image_label.setPixmap(_array_to_pixmap(row.image))
        self.image_label.set_measurement_overlay(result, scale.nm_per_px)
        self.image_label.set_roi(None, visible=False)
        self.result_values_label.setText(_format_result_values(result, scale.nm_per_px))
        self.current_view_mode = "Result View"
        self._sync_view_buttons()
        self.status_label.setText("Measurement completed.")

    def _export_measured_images(self) -> None:
        result = export_measured_batch(self.queue)
        if result.needs_output_folder:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Choose Export Folder",
                "",
            )
            if folder:
                result = export_measured_batch(self.queue, output_folder=Path(folder))
        if result.overwrite_required and result.overwrite_summary is not None:
            if self._confirm_export_overwrite(result.overwrite_summary):
                result = export_measured_batch(
                    self.queue,
                    output_folder=result.output_folder,
                    overwrite_existing=True,
                )
            else:
                self._refresh_file_table()
                self.status_label.setText("Export canceled.")
                return
        self._refresh_file_table()
        self.status_label.setText(result.message)

    def _confirm_export_overwrite(self, summary: OverwriteSummary) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Confirm Export Overwrite")
        dialog.setText(_format_overwrite_dialog_text(summary))
        cancel_button = dialog.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        overwrite_button = dialog.addButton(
            "Overwrite", QMessageBox.ButtonRole.AcceptRole
        )
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() == overwrite_button

    def _show_original_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            self._sync_view_buttons()
            return

        self.image_label.setPixmap(_array_to_pixmap(self.queue.rows[row_index].image))
        self.image_label.set_measurement_overlay(None, None)
        self.image_label.set_roi(self.queue.rows[row_index].roi, visible=True)
        self.result_values_label.setText("")
        self.current_view_mode = "Original View"
        self._sync_view_buttons()

    def _show_result_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            self._sync_view_buttons()
            return

        row = self.queue.rows[row_index]
        if not isinstance(row.measurement_results, MeasurementResult):
            self._sync_view_buttons()
            return

        scale = self.queue.resolve_scale(row_index)
        self.image_label.setPixmap(_array_to_pixmap(row.image))
        self.image_label.set_measurement_overlay(
            row.measurement_results, scale.nm_per_px
        )
        self.image_label.set_roi(None, visible=False)
        self.result_values_label.setText(
            _format_result_values(row.measurement_results, scale.nm_per_px)
        )
        self.current_view_mode = "Result View"
        self._sync_view_buttons()

    def _show_box_plot_view(self) -> None:
        points, warning = _box_plot_points(
            self.queue, self._selected_box_plot_measurement_types()
        )
        self.image_label.set_box_plot(points, warning)
        self.result_values_label.setText(_format_box_plot_summary(points, warning))
        self.current_view_mode = "Box Plot"
        self._sync_view_buttons()

    def _set_all_box_plot_measurement_types(self, checked: bool) -> None:
        for checkbox in self.box_plot_type_checkboxes.values():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(checked)
        self._refresh_box_plot_view_from_filters()

    def _box_plot_type_filter_toggled(self, _checked: bool) -> None:
        all_checked = all(
            checkbox.isChecked()
            for checkbox in self.box_plot_type_checkboxes.values()
        )
        with QSignalBlocker(self.box_plot_select_all_checkbox):
            self.box_plot_select_all_checkbox.setChecked(all_checked)
        self._refresh_box_plot_view_from_filters()

    def _refresh_box_plot_view_from_filters(self) -> None:
        if self.current_view_mode == "Box Plot":
            self._show_box_plot_view()

    def _selected_box_plot_measurement_types(self) -> set[str]:
        return {
            measurement_type
            for measurement_type, checkbox in self.box_plot_type_checkboxes.items()
            if checkbox.isChecked()
        }

    def _show_debug_view(self) -> None:
        row_index = self.file_table.currentRow()
        if row_index < 0 or row_index >= len(self.queue.rows):
            self._sync_view_buttons()
            return

        row = self.queue.rows[row_index]
        if not isinstance(row.measurement_debug, MeasurementResult):
            self._sync_view_buttons()
            return

        self.image_label.setPixmap(_debug_to_pixmap(row.image, row.measurement_debug))
        self.image_label.set_measurement_overlay(None, None)
        self.image_label.set_roi(row.roi, visible=True)
        self.result_values_label.setText(_format_debug_values(row.measurement_debug))
        self.current_view_mode = "Debug View"
        self._sync_view_buttons()

    def _refresh_file_table(self) -> None:
        self.file_table.setRowCount(len(self.queue.rows))
        for row_index, row in enumerate(self.queue.rows):
            values = [
                "",
                "",
                row.group,
                "",
                row.measure_status,
                row.export_status,
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.file_table.setItem(row_index, column_index, item)
            self.file_table.setCellWidget(row_index, 1, _queue_image_widget(row))
            self.file_table.setRowHeight(row_index, 78)

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

    def _sync_view_buttons(self) -> None:
        view_buttons = {
            "Original View": self.original_view_button,
            "Result View": self.result_view_button,
            "Box Plot": self.box_plot_view_button,
            "Debug View": self.debug_view_button,
        }
        for mode, button in view_buttons.items():
            with QSignalBlocker(button):
                button.setChecked(mode == self.current_view_mode)
        self.box_plot_filter_panel.setVisible(self.current_view_mode == "Box Plot")


def create_window() -> MeasurerWindow:
    return MeasurerWindow()


def _queue_image_widget(row) -> QWidget:
    widget = QWidget()
    widget.setObjectName("QueueImageCell")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(5)

    file_row = QHBoxLayout()
    file_row.setContentsMargins(0, 0, 0, 0)
    file_row.setSpacing(8)

    file_name = QLabel(row.file_name)
    file_name.setObjectName("QueueFileName")
    file_name.setToolTip(row.file_name)
    file_name.setWordWrap(False)

    group = QLabel(row.group)
    group.setObjectName("QueueGroupBadge")
    group.setToolTip(f"Group: {row.group}")
    background, border, text = _group_badge_colors(row.group)
    group.setStyleSheet(
        "QLabel#QueueGroupBadge {"
        f"background: {background};"
        f"border: 1px solid {border};"
        f"color: {text};"
        "}"
    )

    file_row.addWidget(file_name, 1)
    file_row.addWidget(group, 0, Qt.AlignmentFlag.AlignRight)

    status_row = QHBoxLayout()
    status_row.setContentsMargins(0, 0, 0, 0)
    status_row.setSpacing(10)
    primary = QLabel(f"{row.roi_status} · {row.measure_status}")
    primary.setObjectName("QueueStatusPrimary")
    primary.setToolTip(
        f"ROI: {row.roi_status}\nMeasure: {row.measure_status}\nExport: {row.export_status}"
    )
    secondary = QLabel(row.export_status)
    secondary.setObjectName("QueueStatusSecondary")
    secondary.setToolTip(primary.toolTip())
    status_row.addWidget(primary)
    status_row.addStretch(1)
    status_row.addWidget(secondary)

    layout.addLayout(file_row)
    layout.addLayout(status_row)
    return widget


def _group_badge_colors(group: str) -> tuple[str, str, str]:
    palettes = [
        ("#193a66", "#2f80ed", "#d7e8ff"),
        ("#3a255f", "#8f5cff", "#eadfff"),
        ("#173f35", "#2bb673", "#d8f7e9"),
        ("#4a3318", "#f2a33a", "#ffedd0"),
        ("#4a2135", "#e85d9f", "#ffe0ef"),
        ("#26364f", "#5aa6ff", "#dcecff"),
    ]
    index = sum(ord(character) for character in group) % len(palettes)
    return palettes[index]


def _roi_is_too_small(roi: RectRoi | None) -> bool:
    if roi is None:
        return False
    return roi.width * roi.height < HARD_MIN_COMPONENT_AREA_PX


def _array_to_pixmap(image: np.ndarray) -> QPixmap:
    display = _normalize_to_uint8(image)
    height, width = display.shape
    bytes_per_line = display.strides[0]
    qimage = QImage(
        display.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8
    ).copy()
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
    values_by_type: dict[str, list[float]] = {
        measurement_type: [] for measurement_type in MEASUREMENT_TYPE_ORDER
    }
    for measurement in result.measurements.values():
        if measurement.status != "success":
            continue
        measurement_type = _measurement_type(measurement)
        if measurement_type is None:
            continue
        values_by_type[measurement_type].append(measurement.value_px * scale)

    parts = []
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


def _format_overwrite_dialog_text(summary: OverwriteSummary) -> str:
    lines = [
        "Existing export files will be overwritten.",
        f"Output folder: {summary.output_folder}",
        "",
        "Targets:",
    ]
    if summary.result_image_count:
        lines.append(
            f"- {summary.result_image_count} "
            f"{_pluralize(summary.result_image_count, 'Result Image')}"
        )
    if summary.debug_image_count:
        lines.append(
            f"- {summary.debug_image_count} "
            f"{_pluralize(summary.debug_image_count, 'Debug Image')}"
        )
    if summary.workbook_count:
        lines.append(f"- {summary.workbook_count} measurements.xlsx")
    return "\n".join(lines)


def _pluralize(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def _box_plot_points(
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
            measurement_type = _measurement_type(measurement)
            if measurement_type is None:
                continue
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


def _box_plot_buckets(
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


def _box_plot_label_clusters(
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


def _box_plot_y(
    value: float, min_value: float, max_value: float, top: int, bottom: int
) -> int:
    fraction = (value - min_value) / (max_value - min_value)
    return round(bottom - fraction * (bottom - top))


def _elided_center_label(metrics, text: str, max_width: int) -> str:
    if max_width <= 0:
        return ""
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)


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


def _stylesheet() -> str:
    return """
    QMainWindow {
        background: #111214;
        color: #f2f3f5;
        font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
        font-size: 13px;
    }

    #Sidebar {
        background: #181a1f;
        border-right: 1px solid #2c3038;
    }

    #PreviewArea {
        background: #101114;
    }

    #Title {
        color: #f6f7f9;
        font-size: 24px;
        font-weight: 600;
    }

    #ImageCanvas {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #15171b;
        color: #aeb4be;
    }

    #StatusCard {
        border: 1px solid #303641;
        border-radius: 8px;
        background: #12151a;
    }

    #StatusTitle {
        color: #f2f4f8;
        font-size: 15px;
        font-weight: 650;
    }

    #ResultValues {
        color: #c9d0db;
        font-size: 13px;
        font-weight: 500;
        padding: 4px 2px;
    }

    #BoxPlotFilters {
        border: 1px solid #303641;
        border-radius: 8px;
        background: #12151a;
    }

    #BoxPlotFilterLabel {
        color: #aeb4be;
        font-weight: 650;
        padding-right: 4px;
    }

    QLabel {
        color: #c9d0db;
    }

    QCheckBox {
        color: #d8dde6;
        spacing: 6px;
    }

    QCheckBox#BoxPlotFilterCheckbox {
        spacing: 9px;
        padding: 0 2px;
    }

    QCheckBox::indicator {
        width: 14px;
        height: 14px;
        border: 1px solid #596170;
        border-radius: 3px;
        background: #151820;
    }

    QCheckBox::indicator:checked {
        border-color: #2f80ed;
        background: #2f80ed;
    }

    QLineEdit {
        min-height: 34px;
        padding: 6px 10px;
        border: 1px solid #3a3f49;
        border-radius: 8px;
        background: #111318;
        color: #eef1f5;
        selection-background-color: #2f80ed;
    }

    QLineEdit:focus {
        border-color: #2f80ed;
    }

    QPushButton {
        min-height: 32px;
        padding: 6px 12px;
        border: 1px solid #3a3f49;
        border-radius: 8px;
        background: #23262d;
        color: #eef1f5;
    }

    QPushButton:hover {
        border-color: #596170;
        background: #2a2e36;
    }

    QPushButton:checked {
        border-color: #2f80ed;
        color: #ffffff;
        background: #1d3f6e;
    }

    QPushButton:disabled {
        border-color: #2b2f36;
        background: #1b1d22;
        color: #737b87;
    }

    #PrimaryButton {
        border: none;
        background: #2f80ed;
        color: #ffffff;
        font-weight: 600;
    }

    #PrimaryButton:hover {
        background: #4a90f3;
    }

    #FileQueue {
        border: 1px solid #2c3038;
        border-radius: 8px;
        background: #111318;
        color: #e4e7ec;
        gridline-color: transparent;
        selection-background-color: #1d3f6e;
        selection-color: #ffffff;
        font-size: 12px;
    }

    #FileQueue::item {
        padding: 4px;
        border-bottom: 1px solid #20242b;
    }

    #QueueImageCell {
        background: transparent;
    }

    #QueueFileName {
        color: #eef2f8;
        font-size: 12px;
        font-weight: 650;
    }

    #QueueGroupBadge {
        border-radius: 6px;
        padding: 2px 7px;
        font-size: 11px;
        font-weight: 650;
    }

    QHeaderView::section {
        border: none;
        border-bottom: 1px solid #303641;
        padding: 6px 4px;
        background: #151820;
        color: #aeb4be;
        font-size: 12px;
        font-weight: 650;
    }
    """


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = create_window()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
