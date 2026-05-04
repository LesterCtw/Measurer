from __future__ import annotations

import numpy as np


def normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return np.ascontiguousarray(image)
    max_value = float(np.max(image))
    if max_value <= 0:
        return np.zeros(image.shape, dtype=np.uint8)
    scaled = np.asarray(image, dtype=np.float32) / max_value * 255
    return np.ascontiguousarray(np.rint(scaled).astype(np.uint8))
