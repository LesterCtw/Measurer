from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, Qt, QSignalBlocker
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

from measurer.image_queue import AddImagesSummary, ImageQueue, RectRoi
from measurer.measurement import MeasurementResult, measure_image


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
        controls.addWidget(self.file_table)
        controls.addWidget(self.status_label)

        workspace = QVBoxLayout()
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
            self.queue.record_measurement_failure(row_index)
            self._refresh_file_table()
            self.file_table.setCurrentCell(row_index, 1)
            self.status_label.setText("Measurement failed.")
            return

        self.queue.record_measurement_result(row_index, result)
        self._refresh_file_table()
        self.file_table.setCurrentCell(row_index, 1)
        scale = self.queue.resolve_scale(row_index)
        self.image_label.setPixmap(_result_to_pixmap(row.image, result))
        self.result_values_label.setText(_format_result_values(result, scale.nm_per_px))
        self.current_view_mode = "Result View"
        self.status_label.setText("Measurement completed.")

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


def _result_to_pixmap(image: np.ndarray, result: MeasurementResult) -> QPixmap:
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
    painter.setPen(QPen(QColor(255, 210, 64), 2))
    for measurement in result.measurements.values():
        painter.drawLine(
            measurement.line.start.x,
            measurement.line.start.y,
            measurement.line.end.x,
            measurement.line.end.y,
        )
        painter.drawText(
            measurement.line.end.x + 4,
            measurement.line.end.y,
            f"{measurement.name} {measurement.value_px:.1f}",
        )
    painter.end()
    return QPixmap.fromImage(qimage)


def _format_result_values(
    result: MeasurementResult, nm_per_px: float | None
) -> str:
    unit = "px" if nm_per_px is None else "nm"
    scale = 1.0 if nm_per_px is None else nm_per_px
    return " | ".join(
        f"{name} {measurement.value_px * scale:.1f} {unit}"
        for name, measurement in result.measurements.items()
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
