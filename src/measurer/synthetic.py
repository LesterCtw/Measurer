from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np


@dataclass(frozen=True)
class SingleMetalIslandSpec:
    image_width: int = 1024
    image_height: int = 1024
    center_x: int = 512
    top_y: int = 256
    height: int = 256
    tcd: int = 120
    bcd: int = 160
    lk_intensity: int = 20
    metal_intensity: int = 220


def create_single_metal_island_image(spec: SingleMetalIslandSpec) -> np.ndarray:
    image = np.full(
        (spec.image_height, spec.image_width),
        spec.lk_intensity,
        dtype=np.uint8,
    )
    top_rows = max(1, ceil(spec.height * 0.2))
    bottom_rows = max(1, ceil(spec.height * 0.05))
    transition_rows = max(1, spec.height - top_rows - bottom_rows)

    for row_offset in range(spec.height):
        y = spec.top_y + row_offset
        if y < 0 or y >= spec.image_height:
            continue

        if row_offset < top_rows:
            width = spec.tcd
        elif row_offset >= spec.height - bottom_rows:
            width = spec.bcd
        else:
            transition_offset = row_offset - top_rows + 1
            fraction = transition_offset / transition_rows
            width = round(spec.tcd + (spec.bcd - spec.tcd) * fraction)

        left = spec.center_x - width // 2
        right = left + width
        left = max(0, left)
        right = min(spec.image_width, right)
        image[y, left:right] = spec.metal_intensity

    return image
