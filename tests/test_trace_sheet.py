import pytest

from measurer.measurement import measure_image
from measurer.roi import RectRoi, RoiSelection
from measurer.synthetic import SingleMetalIslandSpec, create_single_metal_island_image
from measurer.trace_sheet import TRACE_SHEET_HEADER, trace_sheet_row


def test_trace_sheet_row_records_roi_union_metadata():
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
    roi = RoiSelection(
        (
            RectRoi(x=32, y=16, width=64, height=80),
            RectRoi(x=96, y=96, width=24, height=24),
        )
    )
    result = measure_image(image, roi=roi)

    row = trace_sheet_row(
        file_name="roi.tif",
        group="Process A",
        measurement=result.measurements["TCD"],
        measurement_type="TCD",
        target_id="Image",
        result=result,
        scale_source="manual_default",
        scale_nm_per_px=0.5,
        roi=roi,
    )
    values = dict(zip(TRACE_SHEET_HEADER, row, strict=True))

    assert values["file"] == "roi.tif"
    assert values["group"] == "Process A"
    assert values["scale_nm_per_px"] == 0.5
    assert values["scale_source"] == "manual_default"
    assert values["roi_type"] == "union"
    assert values["roi_x_px"] == 32
    assert values["roi_y_px"] == 16
    assert values["roi_width_px"] == 88
    assert values["roi_height_px"] == 104
    assert values["roi_shape_count"] == 2


def test_trace_sheet_row_summarizes_space_pair_refined_boundaries():
    image = create_single_metal_island_image(
        SingleMetalIslandSpec(
            image_width=220,
            image_height=128,
            center_x=60,
            top_y=24,
            height=60,
            tcd=30,
            bcd=42,
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
    measurement = result.measurements["M001-M002 Horizontal Space"]

    row = trace_sheet_row(
        file_name="space.tif",
        group="Default",
        measurement=measurement,
        measurement_type="Horizontal Space",
        target_id="M001-M002",
        result=result,
        scale_source="px",
        scale_nm_per_px=None,
        roi=RoiSelection(),
    )
    values = dict(zip(TRACE_SHEET_HEADER, row, strict=True))
    expected_refined = sum(
        metal.refined_boundary.refined_point_count
        for metal in result.metal_islands
    )
    expected_fallback = sum(
        metal.refined_boundary.fallback_point_count
        for metal in result.metal_islands
    )

    assert values["roi_type"] == "full_image"
    assert values["roi_shape_count"] == 0
    assert values["refined_point_count"] == expected_refined
    assert values["fallback_point_count"] == expected_fallback
    assert values["fallback_ratio"] == pytest.approx(0.0)
