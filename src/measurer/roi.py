from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RectRoi:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PolygonRoi:
    points: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class RoiSelection:
    rectangles: tuple[RectRoi, ...] = ()
    polygons: tuple[PolygonRoi, ...] = ()
    shape_order: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.shape_order:
            return
        object.__setattr__(
            self,
            "shape_order",
            ("rectangle",) * len(self.rectangles)
            + ("polygon",) * len(self.polygons),
        )

    @property
    def is_empty(self) -> bool:
        return len(self.rectangles) == 0 and len(self.polygons) == 0

    @property
    def bounding_box(self) -> RectRoi | None:
        if self.is_empty:
            return None

        boxes = [rect for rect in self.rectangles]
        boxes.extend(
            box
            for polygon in self.polygons
            if (box := polygon_bounding_box(polygon)) is not None
        )
        if not boxes:
            return None

        left = min(rect.x for rect in boxes)
        top = min(rect.y for rect in boxes)
        right = max(rect.x + rect.width for rect in boxes)
        bottom = max(rect.y + rect.height for rect in boxes)
        return RectRoi(x=left, y=top, width=right - left, height=bottom - top)

    def bounding_box_for_image(self, image: np.ndarray) -> RectRoi | None:
        boxes = [
            clamped
            for rectangle in self.rectangles
            if (clamped := clamp_rect_roi_to_image(rectangle, image)) is not None
        ]
        boxes.extend(
            box
            for polygon in self.polygons
            if (clamped := clamp_polygon_roi_to_image(polygon, image)) is not None
            if (box := polygon_bounding_box(clamped)) is not None
        )
        if not boxes:
            return None

        left = min(rect.x for rect in boxes)
        top = min(rect.y for rect in boxes)
        right = max(rect.x + rect.width for rect in boxes)
        bottom = max(rect.y + rect.height for rect in boxes)
        return RectRoi(x=left, y=top, width=right - left, height=bottom - top)


def clamp_rect_roi_to_image(roi: RectRoi, image: np.ndarray) -> RectRoi | None:
    image_height, image_width = image.shape
    left = max(0, roi.x)
    top = max(0, roi.y)
    right = min(image_width, roi.x + roi.width)
    bottom = min(image_height, roi.y + roi.height)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    return RectRoi(x=left, y=top, width=width, height=height)


def clamp_polygon_roi_to_image(
    roi: PolygonRoi, image: np.ndarray
) -> PolygonRoi | None:
    image_height, image_width = image.shape
    clamped_points = tuple(
        (
            min(max(0, int(x)), image_width - 1),
            min(max(0, int(y)), image_height - 1),
        )
        for x, y in roi.points
    )
    if len(set(clamped_points)) < 3:
        return None

    box = polygon_bounding_box(PolygonRoi(clamped_points))
    if box is None or box.width <= 1 or box.height <= 1:
        return None
    return PolygonRoi(clamped_points)


def polygon_bounding_box(roi: PolygonRoi) -> RectRoi | None:
    if len(roi.points) < 3:
        return None

    xs = [point[0] for point in roi.points]
    ys = [point[1] for point in roi.points]
    left = min(xs)
    top = min(ys)
    right = max(xs)
    bottom = max(ys)
    return RectRoi(x=left, y=top, width=right - left + 1, height=bottom - top + 1)


def roi_union_mask(
    roi: RoiSelection, image: np.ndarray, analysis_region: RectRoi
) -> np.ndarray:
    if roi.is_empty:
        return np.ones((analysis_region.height, analysis_region.width), dtype=bool)

    mask = np.zeros((analysis_region.height, analysis_region.width), dtype=bool)
    for rectangle in roi.rectangles:
        clamped = clamp_rect_roi_to_image(rectangle, image)
        if clamped is None:
            continue
        left = max(0, clamped.x - analysis_region.x)
        top = max(0, clamped.y - analysis_region.y)
        right = min(mask.shape[1], left + clamped.width)
        bottom = min(mask.shape[0], top + clamped.height)
        mask[top:bottom, left:right] = True

    for polygon in roi.polygons:
        clamped = clamp_polygon_roi_to_image(polygon, image)
        if clamped is None:
            continue
        mask |= _polygon_mask(clamped, analysis_region)

    return mask


def roi_union_area_px(roi: RoiSelection, image: np.ndarray) -> int:
    if roi.is_empty:
        return image.size

    analysis_region = roi.bounding_box_for_image(image)
    if analysis_region is None:
        return 0

    mask = roi_union_mask(roi, image, analysis_region)
    return int(np.count_nonzero(mask))


def _polygon_mask(roi: PolygonRoi, analysis_region: RectRoi) -> np.ndarray:
    height = analysis_region.height
    width = analysis_region.width
    mask = np.zeros((height, width), dtype=bool)
    points = roi.points
    for local_y in range(height):
        y = analysis_region.y + local_y + 0.5
        for local_x in range(width):
            x = analysis_region.x + local_x + 0.5
            if _point_in_polygon(x, y, points):
                mask[local_y, local_x] = True
    return mask


def _point_in_polygon(
    x: float, y: float, points: tuple[tuple[int, int], ...]
) -> bool:
    inside = False
    previous_x, previous_y = points[-1]
    for current_x, current_y in points:
        crosses_y = (current_y > y) != (previous_y > y)
        if crosses_y:
            edge_x = (previous_x - current_x) * (y - current_y) / (
                previous_y - current_y
            ) + current_x
            if x < edge_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside
