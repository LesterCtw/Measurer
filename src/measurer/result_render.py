from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from measurer.image_display import normalize_to_uint8
from measurer.measurement import MeasurementResult
from measurer.measurement_report import successful_measurement_report_items


def grayscale_rgb_qimage(image: np.ndarray) -> QImage:
    display = normalize_to_uint8(image)
    height, width = display.shape
    rgb = np.ascontiguousarray(np.dstack([display, display, display]))
    return QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format.Format_RGB888,
    ).copy()


def result_qimage(
    image: np.ndarray,
    result: MeasurementResult,
    nm_per_px: float | None,
) -> QImage:
    qimage = grayscale_rgb_qimage(image)
    painter = QPainter(qimage)
    draw_result_measurement_lines(painter, result, nm_per_px)
    painter.end()
    return qimage


def draw_result_measurement_lines(
    painter: QPainter,
    result: MeasurementResult,
    nm_per_px: float | None,
) -> None:
    for item in successful_measurement_report_items(result, nm_per_px):
        measurement = item.measurement
        painter.setPen(QPen(QColor(*item.color_rgb), 2))
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
            item.label,
        )
