import pytest

from measurer.image_queue import RectRoi
from measurer.measurement import measure_image
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
