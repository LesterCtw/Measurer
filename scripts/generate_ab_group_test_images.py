from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile


OUTPUT_DIR = Path.home() / "Desktop" / "ab_group_tif_test_images"
IMAGE_SIZE = 768
NM_PER_PX = 0.8
PIXELS_PER_CM = 10_000_000 / NM_PER_PX


@dataclass(frozen=True)
class IslandSpec:
    center_x: int
    top_y: int
    height: int
    top_width: int
    bottom_width: int
    tilt_px: int = 0


@dataclass(frozen=True)
class ImageSpec:
    group: str
    index: int
    seed: int
    islands: tuple[IslandSpec, ...]
    background: int
    metal: int
    noise_sigma: float
    nm_per_px: float = NM_PER_PX


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = _image_specs()
    manifest_rows: list[dict[str, object]] = []

    for spec in specs:
        image = _render_image(spec)
        file_name = f"group_{spec.group.lower()}_{spec.index:02d}.tif"
        tifffile.imwrite(
            OUTPUT_DIR / file_name,
            image,
            resolution=(PIXELS_PER_CM, PIXELS_PER_CM),
            resolutionunit="CENTIMETER",
        )
        manifest_rows.append(
            {
                "file_name": file_name,
                "group": spec.group,
                "metal_count": len(spec.islands),
                "nm_per_px": spec.nm_per_px,
                "note": "synthetic STEM-like metal islands, top-wide bottom-narrow",
            }
        )

    with (OUTPUT_DIR / "manifest.csv").open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=["file_name", "group", "metal_count", "nm_per_px", "note"]
        )
        writer.writeheader()
        writer.writerows(manifest_rows)


def _image_specs() -> list[ImageSpec]:
    return [
        ImageSpec(
            group="A",
            index=1,
            seed=101,
            background=26,
            metal=208,
            noise_sigma=4.0,
            islands=_grid_islands(seed=101, top_width=76, bottom_width=48, height=138),
        ),
        ImageSpec(
            group="A",
            index=2,
            seed=102,
            background=27,
            metal=214,
            noise_sigma=4.5,
            islands=_grid_islands(seed=102, top_width=80, bottom_width=50, height=144),
        ),
        ImageSpec(
            group="A",
            index=3,
            seed=103,
            background=25,
            metal=204,
            noise_sigma=3.8,
            islands=_grid_islands(seed=103, top_width=72, bottom_width=46, height=136),
        ),
        ImageSpec(
            group="A",
            index=4,
            seed=104,
            background=28,
            metal=216,
            noise_sigma=4.2,
            islands=_grid_islands(seed=104, top_width=78, bottom_width=48, height=142),
        ),
        ImageSpec(
            group="B",
            index=1,
            seed=201,
            background=25,
            metal=212,
            noise_sigma=4.0,
            islands=_grid_islands(seed=201, top_width=104, bottom_width=68, height=154),
        ),
        ImageSpec(
            group="B",
            index=2,
            seed=202,
            background=27,
            metal=218,
            noise_sigma=4.8,
            islands=_grid_islands(seed=202, top_width=110, bottom_width=72, height=160),
        ),
        ImageSpec(
            group="B",
            index=3,
            seed=203,
            background=26,
            metal=210,
            noise_sigma=4.3,
            islands=_grid_islands(seed=203, top_width=100, bottom_width=66, height=150),
        ),
        ImageSpec(
            group="B",
            index=4,
            seed=204,
            background=28,
            metal=220,
            noise_sigma=4.5,
            islands=_grid_islands(seed=204, top_width=106, bottom_width=70, height=156),
        ),
    ]


def _grid_islands(
    seed: int, top_width: int, bottom_width: int, height: int
) -> tuple[IslandSpec, ...]:
    rng = np.random.default_rng(seed)
    centers_x = [112, 292, 476, 656]
    tops_y = [60, 292, 524]
    islands: list[IslandSpec] = []
    for row_index, top_y in enumerate(tops_y):
        for column_index, center_x in enumerate(centers_x):
            islands.append(
                IslandSpec(
                    center_x=center_x + int(rng.integers(-14, 15)),
                    top_y=top_y + int(rng.integers(-12, 13)),
                    height=height + int(rng.integers(-8, 9)),
                    top_width=top_width + int(rng.integers(-6, 7)),
                    bottom_width=bottom_width + int(rng.integers(-5, 6)),
                    tilt_px=int(rng.integers(-7, 8)),
                )
            )
    return tuple(islands)


def _render_image(spec: ImageSpec) -> np.ndarray:
    rng = np.random.default_rng(spec.seed)
    image = rng.normal(
        loc=spec.background,
        scale=spec.noise_sigma,
        size=(IMAGE_SIZE, IMAGE_SIZE),
    )
    image += _low_frequency_texture(rng) * 5.0

    for island in spec.islands:
        _draw_island(image, island, spec.metal, rng)

    _add_faint_scan_lines(image, rng)
    return np.clip(image, 0, 255).astype(np.uint8)


def _draw_island(
    image: np.ndarray, island: IslandSpec, metal_intensity: int, rng: np.random.Generator
) -> None:
    edge_walk = rng.normal(0.0, 1.0, island.height + 2).cumsum()
    edge_walk -= edge_walk.mean()
    edge_walk = np.clip(edge_walk, -5.0, 5.0)

    for row_offset in range(island.height):
        y = island.top_y + row_offset
        if y < 0 or y >= image.shape[0]:
            continue

        fraction = row_offset / max(1, island.height - 1)
        width = island.top_width + (island.bottom_width - island.top_width) * fraction
        width += 2.0 * np.sin(fraction * np.pi * 2.0 + island.center_x / 37.0)
        center = island.center_x + round(island.tilt_px * (fraction - 0.5))
        edge_noise = edge_walk[row_offset]
        left = round(center - width / 2 + edge_noise)
        right = round(center + width / 2 + edge_noise * 0.4)
        left = max(0, left)
        right = min(image.shape[1], right)
        if right <= left:
            continue

        row_noise = rng.normal(0.0, 3.0, right - left)
        image[y, left:right] = metal_intensity + row_noise

        if left > 0:
            image[y, left - 1] = (image[y, left - 1] + metal_intensity) / 2
        if right < image.shape[1]:
            image[y, right] = (image[y, right] + metal_intensity) / 2


def _low_frequency_texture(rng: np.random.Generator) -> np.ndarray:
    coarse_size = 32
    tile_size = int(np.ceil(IMAGE_SIZE / coarse_size))
    coarse = rng.normal(0.0, 1.0, size=(coarse_size, coarse_size))
    return np.kron(coarse, np.ones((tile_size, tile_size)))[:IMAGE_SIZE, :IMAGE_SIZE]


def _add_faint_scan_lines(image: np.ndarray, rng: np.random.Generator) -> None:
    for y in range(0, image.shape[0], 16):
        image[y : y + 1, :] += rng.normal(0.0, 1.5)


if __name__ == "__main__":
    main()
