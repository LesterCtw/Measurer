import numpy as np
import pytest

from measurer.image_queue import RectRoi, RoiSelection
from measurer.measurement import (
    MeasurementConfig,
    Point,
    _measure_single_metal_island,
    measure_image,
)
from measurer.synthetic import SingleMetalIslandSpec, create_single_metal_island_image


def test_measure_clean_single_metal_island_full_image():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=64,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(image, roi=None)

    assert result.status == "success"
    assert result.analysis_region == RectRoi(x=0, y=0, width=128, height=128)
    assert result.refined_boundary.points[0] == result.refined_boundary.points[-1]
    assert len(result.refined_boundary.points) > 4
    assert result.refined_boundary.refined_point_count > 0
    assert result.refined_boundary.fallback_point_count == 0
    assert result.refined_boundary.fallback_ratio == pytest.approx(0.0)
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_bcd_uses_bottom_five_percent_region():
    mask = np.zeros((140, 160), dtype=bool)
    spans: dict[int, tuple[int, int]] = {}

    for y in range(20, 120):
        width = 32
        if 110 <= y < 115:
            width = 80
        elif y >= 115:
            width = 40

        left = 80 - width // 2
        right = left + width - 1
        mask[y, left : right + 1] = True
        spans[y] = (left, right)

    measurements = _measure_single_metal_island(
        spans,
        mask,
        RectRoi(x=0, y=0, width=160, height=140),
    )

    assert measurements["BCD"].value_px == pytest.approx(40)
    assert measurements["BCD"].line.start.y >= 115


def test_custom_roi_limits_the_analysis_region():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=160,
            image_height=128,
            center_x=54,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    image[20:95, 120:150] = 255

    result = measure_image(image, roi=RectRoi(x=20, y=16, width=72, height=88))

    assert result.status == "success"
    assert result.analysis_region == RectRoi(x=20, y=16, width=72, height=88)
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_rectangle_roi_union_ignores_pixels_outside_selected_shapes():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=180,
            image_height=128,
            center_x=54,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    image[20:95, 120:150] = 255

    result = measure_image(
        image,
        roi=RoiSelection(
            (
                RectRoi(x=20, y=16, width=72, height=88),
                RectRoi(x=160, y=16, width=10, height=88),
            )
        ),
    )

    assert result.status == "success"
    assert result.analysis_region == RectRoi(x=20, y=16, width=150, height=88)
    assert len(result.metal_islands) == 1
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_overlapping_rectangle_roi_shapes_do_not_duplicate_measurements():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=64,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(
        image,
        roi=RoiSelection(
            (
                RectRoi(x=20, y=16, width=70, height=88),
                RectRoi(x=35, y=16, width=70, height=88),
            )
        ),
    )

    assert result.status == "success"
    assert len(result.metal_islands) == 1
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_insufficient_refinement_samples_fall_back_without_failing_measurement():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=40,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(image, roi=RectRoi(x=13, y=16, width=80, height=88))

    assert result.status == "success"
    assert result.refined_boundary.fallback_point_count > 0
    assert result.refined_boundary.refined_point_count > 0
    assert result.refined_boundary.fallback_ratio > 0
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_high_fallback_ratio_still_reports_successful_measurements():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=64,
            top_y=24,
            height=60,
            tcd=48,
            bcd=48,
        )
    )

    result = measure_image(image, roi=RectRoi(x=37, y=16, width=54, height=88))

    assert result.status == "success"
    assert result.refined_boundary.fallback_ratio == pytest.approx(1.0)
    assert result.measurements["TCD"].value_px == pytest.approx(48)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_low_contrast_refinement_falls_back_without_failing_measurement():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=64,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(
        image,
        roi=None,
        config=MeasurementConfig(min_refinement_contrast=255),
    )

    assert result.status == "success"
    assert result.refined_boundary.fallback_ratio == pytest.approx(1.0)
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_small_bright_contamination_is_excluded_from_metal_island_measurement():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=160,
            image_height=128,
            center_x=80,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    image[8:14, 8:14] = 255

    result = measure_image(image, roi=None)

    assert result.status == "success"
    assert result.measurements["TCD"].value_px == pytest.approx(32)
    assert result.measurements["BCD"].value_px == pytest.approx(48)
    assert result.measurements["Height"].value_px == pytest.approx(60)


def test_metal_island_touching_roi_boundary_is_excluded():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=160,
            image_height=128,
            center_x=80,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(image, roi=RectRoi(x=64, y=20, width=80, height=80))

    assert result.status == "failed"
    assert result.failure_reason == "No metal candidates"
    assert result.measurements == {}


def test_metal_island_touching_full_image_boundary_is_excluded():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=16,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )

    result = measure_image(image, roi=None)

    assert result.status == "failed"
    assert result.failure_reason == "No metal candidates"
    assert result.measurements == {}


def test_image_without_metal_candidates_fails_with_reason():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=128,
            image_height=128,
            center_x=64,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
            lk_intensity=20,
            metal_intensity=20,
        )
    )

    result = measure_image(image, roi=None)

    assert result.status == "failed"
    assert result.failure_reason == "No metal candidates"
    assert result.measurements == {}


def test_median_relative_area_filter_excludes_medium_contamination():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=320,
            image_height=220,
            center_x=80,
            top_y=48,
            height=90,
            tcd=80,
            bcd=100,
        )
    )
    image[48:148, 180:230] = 220
    image[48:148, 250:300] = 220
    image[8:18, 8:19] = 255

    result = measure_image(image, roi=None)

    assert result.status == "success"
    assert result.detection is not None
    excluded_areas = [
        component.area_px
        for component in result.detection.excluded_small_components
    ]
    assert 110 in excluded_areas


def test_min_area_ratio_to_median_can_be_configured():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=320,
            image_height=220,
            center_x=80,
            top_y=48,
            height=90,
            tcd=80,
            bcd=100,
        )
    )
    image[48:148, 220:270] = 220
    image[8:28, 8:33] = 255

    result = measure_image(
        image,
        roi=None,
        config=MeasurementConfig(min_area_ratio_to_median=0.2),
    )

    assert result.status == "success"
    assert result.detection is not None
    excluded_areas = [
        component.area_px
        for component in result.detection.excluded_small_components
    ]
    assert 500 in excluded_areas


def test_measure_multiple_metal_islands_in_one_row_with_stable_ids():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=128,
            center_x=60,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    right_image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=128,
            center_x=150,
            top_y=24,
            height=60,
            tcd=30,
            bcd=42,
        )
    )
    image = image.copy()
    image[right_image == 220] = 220

    result = measure_image(image, roi=None)

    assert result.status == "success"
    assert [metal.id for metal in result.metal_islands] == ["M001", "M002"]
    assert result.metal_islands[0].measurements["TCD"].value_px == pytest.approx(32)
    assert result.metal_islands[0].measurements["BCD"].value_px == pytest.approx(48)
    assert result.metal_islands[0].measurements["Height"].value_px == pytest.approx(60)
    assert result.metal_islands[1].measurements["TCD"].value_px == pytest.approx(30)
    assert result.metal_islands[1].measurements["BCD"].value_px == pytest.approx(42)
    assert result.metal_islands[1].measurements["Height"].value_px == pytest.approx(60)


def test_measure_horizontal_space_between_same_row_adjacent_metal_islands():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=128,
            center_x=60,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    right_image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=128,
            center_x=150,
            top_y=24,
            height=60,
            tcd=30,
            bcd=42,
        )
    )
    image = image.copy()
    image[right_image == 220] = 220

    result = measure_image(image, roi=None)

    assert result.measurements["M001-M002 Horizontal Space"].value_px == pytest.approx(44)


def test_horizontal_space_line_uses_refined_bbox_gap_between_tcd_lines():
    image = np.full((140, 260), 20, dtype=np.uint8)
    image[20:42, 45:81] = 220
    image[42:101, 40:91] = 220
    image[20:42, 150:186] = 220
    image[42:101, 130:191] = 220

    result = measure_image(image, roi=None)

    left_metal = result.metal_islands[0]
    right_metal = result.metal_islands[1]
    left_bbox_max_x = max(point.x for point in left_metal.refined_boundary.points)
    right_bbox_min_x = min(point.x for point in right_metal.refined_boundary.points)
    left_tcd_y = left_metal.measurements["TCD"].line.end.y
    right_tcd_y = right_metal.measurements["TCD"].line.start.y
    expected_y = round((left_tcd_y + right_tcd_y) / 2)
    line = result.measurements["M001-M002 Horizontal Space"].line

    assert line.start.x == left_bbox_max_x
    assert line.end.x == right_bbox_min_x
    assert line.start.y == expected_y
    assert line.end.y == expected_y
    assert result.measurements["M001-M002 Horizontal Space"].value_px == pytest.approx(
        line.end.x - line.start.x
    )


def test_horizontal_space_line_sits_midway_between_offset_tcd_lines():
    image = np.full((560, 360), 20, dtype=np.uint8)
    image[200:240, 70:111] = 220
    image[240:400, 60:121] = 220
    image[300:340, 230:271] = 220
    image[340:500, 220:281] = 220

    result = measure_image(image, roi=None)

    left_tcd_y = result.metal_islands[0].measurements["TCD"].line.end.y
    right_tcd_y = result.metal_islands[1].measurements["TCD"].line.start.y
    line = result.measurements["M001-M002 Horizontal Space"].line

    assert left_tcd_y == 200
    assert right_tcd_y == 300
    assert line.start.y == 250
    assert line.end.y == 250


def test_measure_vertical_space_between_same_column_adjacent_metal_islands():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=180,
            image_height=180,
            center_x=90,
            top_y=20,
            height=50,
            tcd=32,
            bcd=42,
        )
    )
    lower_image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=180,
            image_height=180,
            center_x=90,
            top_y=100,
            height=50,
            tcd=32,
            bcd=42,
        )
    )
    image = image.copy()
    image[lower_image == 220] = 220

    result = measure_image(image, roi=None)

    assert [metal.id for metal in result.metal_islands] == ["M001", "M002"]
    assert result.measurements["M001-M002 Vertical Space"].value_px == pytest.approx(30)


def test_vertical_space_line_stays_inside_lk_gap():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=180,
            image_height=180,
            center_x=90,
            top_y=20,
            height=50,
            tcd=32,
            bcd=42,
        )
    )
    lower_image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=180,
            image_height=180,
            center_x=90,
            top_y=100,
            height=50,
            tcd=32,
            bcd=42,
        )
    )
    image = image.copy()
    image[lower_image == 220] = 220

    result = measure_image(image, roi=None)

    line = result.measurements["M001-M002 Vertical Space"].line
    assert line.start == Point(x=90, y=70)
    assert line.end == Point(x=90, y=99)
    assert image[line.start.y, line.start.x] == 20
    assert image[line.end.y, line.end.x] == 20


def test_invalid_overlap_pair_is_omitted_without_failing_image():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=160,
            center_x=60,
            top_y=24,
            height=60,
            tcd=32,
            bcd=48,
        )
    )
    offset_image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=160,
            center_x=150,
            top_y=69,
            height=60,
            tcd=30,
            bcd=42,
        )
    )
    image = image.copy()
    image[offset_image == 220] = 220

    result = measure_image(image, roi=None)

    assert result.status == "success"
    assert [metal.id for metal in result.metal_islands] == ["M001", "M002"]
    assert "M001-M002 Horizontal Space" not in result.measurements
    assert result.rejected_space_pairs[0].pair_name == "M001-M002"
    assert result.rejected_space_pairs[0].measurement_type == "Horizontal Space"
    assert result.rejected_space_pairs[0].reason == "Insufficient y-overlap."
    assert result.metal_islands[0].measurements["Height"].value_px == pytest.approx(60)
    assert result.metal_islands[1].measurements["Height"].value_px == pytest.approx(60)


def test_metal_island_ids_are_top_to_bottom_then_left_to_right_within_rows():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=240,
            image_height=220,
            center_x=60,
            top_y=24,
            height=50,
            tcd=30,
            bcd=40,
        )
    )
    for center_x, top_y in [(150, 28), (55, 126), (148, 122)]:
        island_image = create_single_metal_island_image(
            SingleMetalIslandSpec(
                image_width=240,
                image_height=220,
                center_x=center_x,
                top_y=top_y,
                height=50,
                tcd=30,
                bcd=40,
            )
        )
        image[island_image == 220] = 220

    result = measure_image(image, roi=None)

    assert [metal.id for metal in result.metal_islands] == [
        "M001",
        "M002",
        "M003",
        "M004",
    ]
    assert [
        measurement.value_px
        for measurement in result.measurements.values()
        if measurement.name.endswith("TCD")
    ] == pytest.approx([30, 30, 30, 30])
