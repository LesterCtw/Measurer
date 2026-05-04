from measurer.measurement import (
    Measurement,
    MeasurementLine,
    MeasurementResult,
    Point,
    RefinedBoundary,
)
from measurer.measurement_report import (
    MEASUREMENT_TYPE_COLORS,
    MEASUREMENT_TYPE_ORDER,
    format_measurement_summary,
    measurement_report_key,
    successful_measurement_report_items,
)
from measurer.roi import RectRoi


def _measurement(name: str) -> Measurement:
    return Measurement(
        name=name,
        value_px=1.0,
        line=MeasurementLine(start=Point(0, 0), end=Point(1, 0)),
    )


def _result(measurements: dict[str, Measurement]) -> MeasurementResult:
    return MeasurementResult(
        status="success",
        analysis_region=RectRoi(x=0, y=0, width=10, height=10),
        refined_boundary=RefinedBoundary(points=[]),
        measurements=measurements,
    )


def test_measurement_report_key_extracts_type_and_target_id():
    report_key = measurement_report_key(_measurement("M001-M002 Horizontal Space"))

    assert report_key is not None
    assert report_key.measurement_type == "Horizontal Space"
    assert report_key.target_id == "M001-M002"


def test_measurement_report_key_defaults_single_metal_island_target_id():
    report_key = measurement_report_key(_measurement("TCD"))

    assert report_key is not None
    assert report_key.measurement_type == "TCD"
    assert report_key.target_id == "M001"


def test_measurement_report_defines_all_display_colors():
    assert set(MEASUREMENT_TYPE_COLORS) == set(MEASUREMENT_TYPE_ORDER)


def test_successful_measurement_report_items_apply_scale_label_and_color():
    result = _result(
        {
            "TCD": Measurement(
                name="M002 TCD",
                value_px=10.0,
                line=MeasurementLine(start=Point(1, 2), end=Point(11, 2)),
            ),
            "failed": Measurement(
                name="M002 BCD",
                value_px=float("nan"),
                line=MeasurementLine(start=Point(1, 8), end=Point(11, 8)),
                status="failed",
            ),
        }
    )

    items = successful_measurement_report_items(result, nm_per_px=0.5)

    assert len(items) == 1
    assert items[0].measurement_type == "TCD"
    assert items[0].target_id == "M002"
    assert items[0].display_value == 5.0
    assert items[0].unit == "nm"
    assert items[0].label == "5.0 nm"
    assert items[0].color_rgb == MEASUREMENT_TYPE_COLORS["TCD"]


def test_format_measurement_summary_groups_values_by_measurement_type():
    result = _result(
        {
            "first": Measurement(
                name="M001 TCD",
                value_px=10.0,
                line=MeasurementLine(start=Point(0, 0), end=Point(10, 0)),
            ),
            "second": Measurement(
                name="M002 TCD",
                value_px=20.0,
                line=MeasurementLine(start=Point(0, 1), end=Point(20, 1)),
            ),
            "height": Measurement(
                name="M001 Height",
                value_px=30.0,
                line=MeasurementLine(start=Point(5, 0), end=Point(5, 30)),
            ),
        }
    )

    assert (
        format_measurement_summary(result, nm_per_px=None)
        == "TCD: 10.0-20.0 px (n=2) | Height: 30.0 px (n=1)"
    )
