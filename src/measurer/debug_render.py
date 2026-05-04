from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from measurer.image_display import normalize_to_uint8
from measurer.measurement import MeasurementResult
from measurer.result_render import (
    grayscale_rgb_qimage,
    result_qimage,
)
from measurer.roi import RectRoi


def debug_view_qimage(image: np.ndarray, result: MeasurementResult) -> QImage:
    qimage = rough_mask_qimage(image, result, blend=True)
    painter = QPainter(qimage)
    draw_candidate_boxes(painter, result)
    draw_boundary_points(painter, result)
    painter.end()
    return qimage


def debug_panel_qimage(image: np.ndarray, result: MeasurementResult) -> QImage:
    original = grayscale_rgb_qimage(image)
    width = original.width()
    height = original.height()
    debug_image = QImage(width * 2, height * 2, QImage.Format.Format_RGB888)
    debug_image.fill(QColor(18, 22, 28))

    painter = QPainter(debug_image)
    painter.drawImage(0, 0, original)
    painter.drawImage(width, 0, rough_mask_qimage(image, result))
    painter.drawImage(0, height, candidate_boxes_qimage(image, result))
    painter.drawImage(width, height, result_qimage(image, result, nm_per_px=None))
    painter.end()
    return debug_image


def rough_mask_qimage(
    image: np.ndarray,
    result: MeasurementResult,
    *,
    blend: bool = False,
) -> QImage:
    if not blend:
        qimage = grayscale_rgb_qimage(image)
        if result.detection is None:
            return qimage

        painter = QPainter(qimage)
        painter.setPen(QPen(QColor(24, 96, 180), 1))
        region = result.analysis_region
        ys, xs = np.where(result.detection.rough_mask)
        for x, y in zip(xs, ys, strict=False):
            painter.drawPoint(region.x + int(x), region.y + int(y))
        painter.end()
        return qimage

    if result.detection is None:
        return grayscale_rgb_qimage(image)

    display = normalize_to_uint8(image)
    height, width = display.shape
    rgb = np.ascontiguousarray(np.dstack([display, display, display]))
    region = result.analysis_region
    region_rgb = rgb[
        region.y : region.y + region.height,
        region.x : region.x + region.width,
    ]
    rough_mask = result.detection.rough_mask
    region_rgb[rough_mask] = (
        region_rgb[rough_mask].astype(np.uint16) // 2
        + np.asarray([24, 96, 180], dtype=np.uint16)
    ).astype(np.uint8)
    return QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format.Format_RGB888,
    ).copy()


def candidate_boxes_qimage(image: np.ndarray, result: MeasurementResult) -> QImage:
    qimage = grayscale_rgb_qimage(image)
    painter = QPainter(qimage)
    draw_candidate_boxes(painter, result)
    painter.end()
    return qimage


def draw_candidate_boxes(painter: QPainter, result: MeasurementResult) -> None:
    if result.detection is None:
        return

    for candidates, color in [
        (result.detection.kept_candidates, QColor(80, 220, 120)),
        (result.detection.excluded_small_components, QColor(255, 190, 64)),
        (result.detection.excluded_boundary_touch_components, QColor(255, 80, 80)),
    ]:
        _draw_component_boxes(painter, result.analysis_region, candidates, color)


def draw_boundary_points(painter: QPainter, result: MeasurementResult) -> None:
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
    painter: QPainter,
    analysis_region: RectRoi,
    candidates,
    color: QColor,
) -> None:
    painter.setPen(QPen(color, 2))
    for candidate in candidates:
        min_x, min_y, max_x, max_y = candidate.bbox
        painter.drawRect(
            analysis_region.x + min_x,
            analysis_region.y + min_y,
            max_x - min_x + 1,
            max_y - min_y + 1,
        )
