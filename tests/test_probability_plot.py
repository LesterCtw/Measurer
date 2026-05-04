import numpy as np

from measurer.image_queue import ImageQueue
from measurer.measurement import (
    Measurement,
    MeasurementLine,
    MeasurementResult,
    Point,
    RefinedBoundary,
)
from measurer.probability_plot import (
    ProbabilityPlotPoint,
    format_probability_plot_summary,
    normal_probability_score,
    probability_plot_buckets,
    probability_plot_points,
)
from measurer.roi import RectRoi


def _measurement(name: str, value_px: float, status: str = "success") -> Measurement:
    return Measurement(
        name=name,
        value_px=value_px,
        line=MeasurementLine(start=Point(0, 0), end=Point(round(value_px), 0)),
        status=status,
    )


def _result(measurements: dict[str, Measurement]) -> MeasurementResult:
    return MeasurementResult(
        status="success",
        analysis_region=RectRoi(x=0, y=0, width=10, height=10),
        refined_boundary=RefinedBoundary(points=[]),
        measurements=measurements,
    )


def test_probability_plot_points_use_successful_final_measurements_only(tmp_path):
    queue = ImageQueue()
    queue.add_image_data(tmp_path / "first.tif", np.ones((10, 10), dtype=np.uint8))
    queue.set_group([0], "Process A")
    queue.record_measurement_result(
        0,
        _result(
            {
                "tcd": _measurement("M001 TCD", 12.0),
                "failed_bcd": _measurement("M001 BCD", 30.0, status="failed"),
            }
        ),
    )

    points, warning = probability_plot_points(queue)

    assert warning == ""
    assert [
        (point.group, point.measurement_type, point.value, point.unit)
        for point in points
    ] == [
        ("Process A", "TCD", 12.0, "px")
    ]
    assert (
        format_probability_plot_summary(points, warning)
        == "P-Chart: 1 measurement | Unit: px | Groups: Process A | Types: TCD"
    )


def test_probability_plot_buckets_sort_values_and_mark_insufficient_data():
    points, warning = probability_plot_points_for_values(
        [
            ("LF", "BCD", 6.0),
            ("EF", "BCD", 4.0),
            ("LF", "TCD", 12.0),
            ("EF", "TCD", 9.0),
            ("EF", "TCD", 7.0),
        ]
    )

    buckets = probability_plot_buckets(points)

    assert warning == ""
    assert [bucket.key for bucket in buckets] == [
        ("EF", "TCD"),
        ("LF", "TCD"),
        ("EF", "BCD"),
        ("LF", "BCD"),
    ]
    assert buckets[0].points[0].value == 7.0
    assert buckets[0].points[1].value == 9.0
    assert (
        buckets[0].points[0].probability_percent
        < buckets[0].points[1].probability_percent
    )
    assert buckets[0].drawable is True
    assert buckets[1].drawable is False


def test_normal_probability_score_maps_percent_to_standard_normal_scale():
    assert normal_probability_score(50.0) == 0.0
    assert round(normal_probability_score(84.1344746), 3) == 1.0
    assert round(normal_probability_score(15.8655254), 3) == -1.0


def test_probability_plot_warns_when_no_measurement_types_are_selected(tmp_path):
    queue = ImageQueue()
    queue.add_image_data(tmp_path / "first.tif", np.ones((10, 10), dtype=np.uint8))

    points, warning = probability_plot_points(queue, selected_measurement_types=set())

    assert points == []
    assert warning == "P-Chart: no selected measurement types."


def test_probability_plot_warns_instead_of_mixing_nm_and_px(tmp_path):
    queue = ImageQueue()
    image = np.ones((10, 10), dtype=np.uint8)
    queue.add_image_data(tmp_path / "scaled.tif", image, metadata_nm_per_px=0.5)
    queue.add_image_data(tmp_path / "unscaled.tif", image)
    for row_index in range(2):
        queue.record_measurement_result(
            row_index,
            _result({"tcd": _measurement("M001 TCD", 10.0)}),
        )

    points, warning = probability_plot_points(queue)

    assert len(points) == 2
    assert warning == "P-Chart cannot mix nm and px measurements."


def probability_plot_points_for_values(
    values: list[tuple[str, str, float]]
) -> tuple[list[ProbabilityPlotPoint], str]:
    queue = ImageQueue()
    for index, (group, measurement_type, value_px) in enumerate(values):
        queue.add_image_data(
            f"/tmp/probability_plot_{index}.tif",
            np.ones((10, 10), dtype=np.uint8),
        )
        queue.set_group([index], group)
        queue.record_measurement_result(
            index,
            _result(
                {measurement_type: _measurement(f"M001 {measurement_type}", value_px)}
            ),
        )
    return probability_plot_points(queue)
