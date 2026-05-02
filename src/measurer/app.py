from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from measurer.image_queue import AddImagesSummary, ImageQueue


class MeasurerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Measurer")
        self.queue = ImageQueue()

        self.add_images_button = QPushButton("Add Images")
        self.add_images_button.clicked.connect(self._choose_images)
        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(
            ["Select", "File", "Group", "ROI", "Measure", "Export"]
        )
        self.file_table.currentCellChanged.connect(self._show_selected_image)
        self.status_label = QLabel("No images added.")
        self.image_label = QLabel("Original")

        controls = QVBoxLayout()
        controls.addWidget(self.add_images_button)
        controls.addWidget(self.file_table)
        controls.addWidget(self.status_label)

        workspace = QVBoxLayout()
        workspace.addWidget(self.image_label)

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
            self._show_selected_image(self.file_table.currentRow())
        return summary

    def _show_selected_image(
        self,
        current_row: int,
        _current_column: int = 0,
        _previous_row: int = 0,
        _previous_column: int = 0,
    ) -> None:
        if current_row < 0 or current_row >= len(self.queue.rows):
            return
        self.image_label.setPixmap(_array_to_pixmap(self.queue.rows[current_row].image))

    def _choose_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Images",
            "",
            "TIFF Images (*.tif *.tiff)",
        )
        if paths:
            self.add_image_paths(paths)

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
