import pytest

from measurer.image_queue import RectRoi
from measurer.measurement import MeasurementConfig, measure_image
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
