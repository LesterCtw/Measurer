import numpy as np
import tifffile

from measurer.image_queue import ImageQueue, PolygonRoi, RectRoi, ScaleResolution


def test_add_images_accepts_dm3_2d_image_with_px_fallback(monkeypatch, tmp_path):
    image_path = tmp_path / "stem_zc.dm3"
    image_path.write_bytes(b"fake dm3")
    dm3_image = np.arange(16, dtype=np.uint8).reshape(4, 4)

    def fake_file_reader(filename):
        assert filename == str(image_path.resolve())
        return [{"data": dm3_image, "axes": []}]

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 1
    assert summary.skipped_count == 0
    assert queue.rows[0].file_name == "stem_zc.dm3"
    assert np.array_equal(queue.rows[0].image, dm3_image)
    assert queue.resolve_scale(0) == ScaleResolution(source="px", nm_per_px=None)


def test_add_images_skips_unreadable_dm3_without_blocking_valid_files(
    monkeypatch, tmp_path
):
    dm3_path = tmp_path / "bad.dm3"
    dm3_path.write_bytes(b"bad dm3")
    tiff_path = tmp_path / "valid.tif"
    tifffile.imwrite(tiff_path, np.ones((4, 4), dtype=np.uint8))

    def fake_file_reader(filename):
        raise OSError(f"cannot read {filename}")

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )

    queue = ImageQueue()
    summary = queue.add_images([dm3_path, tiff_path])

    assert summary.added_count == 1
    assert summary.skipped_reasons == {"failed to read image data": 1}
    assert [row.file_name for row in queue.rows] == ["valid.tif"]


def test_add_images_skips_dm3_unsupported_shape(monkeypatch, tmp_path):
    image_path = tmp_path / "stack.dm3"
    image_path.write_bytes(b"fake stack dm3")

    def fake_file_reader(filename):
        return [{"data": np.ones((2, 4, 5), dtype=np.uint8), "axes": []}]

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 0
    assert summary.skipped_reasons == {"unsupported image shape": 1}
    assert queue.rows == []


def test_dm3_metadata_scale_takes_priority_and_blocks_manual_override(
    monkeypatch, tmp_path
):
    image_path = tmp_path / "metadata_scale.dm3"
    image_path.write_bytes(b"fake dm3")

    def fake_file_reader(filename):
        return [
            {
                "data": np.ones((4, 4), dtype=np.uint8),
                "axes": [
                    {"name": "y", "scale": 0.8, "units": "nm"},
                    {"name": "x", "scale": 0.8, "units": "nm"},
                ],
            }
        ]

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 1
    assert queue.resolve_scale(0) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )
    assert queue.set_manual_scale(0, "0.5") is False
    assert queue.resolve_scale(0) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )


def test_dm3_without_metadata_allows_manual_scale_after_px_fallback(
    monkeypatch, tmp_path
):
    image_path = tmp_path / "no_metadata_scale.dm3"
    image_path.write_bytes(b"fake dm3")

    def fake_file_reader(filename):
        return [{"data": np.ones((4, 4), dtype=np.uint8), "axes": []}]

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )

    queue = ImageQueue()
    queue.add_images([image_path])

    assert queue.resolve_scale(0) == ScaleResolution(source="px", nm_per_px=None)
    assert queue.set_manual_scale(0, "0.5") is True
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.5
    )


def test_add_images_accepts_valid_2d_tiff(tmp_path):
    image_path = tmp_path / "stem_zc.tif"
    tifffile.imwrite(image_path, np.arange(16, dtype=np.uint8).reshape(4, 4))

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 1
    assert summary.skipped_count == 0
    assert summary.message == "Added 1 image."

    row = queue.rows[0]
    assert row.path == image_path.resolve()
    assert row.file_name == "stem_zc.tif"
    assert row.group == "Default"
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.image.shape == (4, 4)


def test_add_images_reads_tiff_centimeter_resolution_as_nm_per_px(tmp_path):
    image_path = tmp_path / "metadata_scale.tif"
    image = np.arange(16, dtype=np.uint8).reshape(4, 4)
    nm_per_px = 0.8
    pixels_per_cm = 10_000_000 / nm_per_px
    tifffile.imwrite(
        image_path,
        image,
        resolution=(pixels_per_cm, pixels_per_cm),
        resolutionunit="CENTIMETER",
    )

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 1
    assert queue.resolve_scale(0) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )


def test_add_images_converts_rgb_tiff_to_grayscale(tmp_path):
    image_path = tmp_path / "rgb_stem_zc.tif"
    rgb = np.zeros((3, 2, 3), dtype=np.uint8)
    rgb[:, :, 0] = 30
    rgb[:, :, 1] = 60
    rgb[:, :, 2] = 90
    tifffile.imwrite(image_path, rgb)

    queue = ImageQueue()
    summary = queue.add_images([image_path])

    assert summary.added_count == 1
    assert summary.skipped_count == 0
    assert queue.rows[0].image.shape == (3, 2)
    assert queue.rows[0].image.dtype == np.uint8


def test_add_images_skips_unsupported_shape_and_unreadable_files(tmp_path):
    valid_path = tmp_path / "valid.tif"
    stack_path = tmp_path / "stack.tif"
    unreadable_path = tmp_path / "not_an_image.tif"
    tifffile.imwrite(valid_path, np.ones((4, 4), dtype=np.uint16))
    tifffile.imwrite(stack_path, np.ones((2, 4, 5), dtype=np.uint8))
    unreadable_path.write_text("not a tiff", encoding="utf-8")

    queue = ImageQueue()
    summary = queue.add_images([stack_path, valid_path, unreadable_path])

    assert summary.added_count == 1
    assert summary.skipped_count == 2
    assert summary.skipped_reasons == {
        "unsupported image shape": 1,
        "failed to read image data": 1,
    }
    assert summary.message == (
        "Added 1 image. Skipped 2 files: "
        "1 unsupported image shape, 1 failed to read image data."
    )
    assert [row.file_name for row in queue.rows] == ["valid.tif"]
    assert queue.rows[0].image.dtype == np.uint16


def test_add_images_skips_multi_page_tiff(tmp_path):
    multi_page_path = tmp_path / "multi_page.tif"
    with tifffile.TiffWriter(multi_page_path) as tiff:
        tiff.write(np.ones((4, 4), dtype=np.uint8))
        tiff.write(np.ones((4, 4), dtype=np.uint8) * 2)

    queue = ImageQueue()
    summary = queue.add_images([multi_page_path])

    assert summary.added_count == 0
    assert summary.skipped_reasons == {"unsupported image shape": 1}
    assert queue.rows == []


def test_add_images_ignores_duplicate_absolute_paths_without_resetting_rows(tmp_path):
    image_path = tmp_path / "duplicate.tif"
    tifffile.imwrite(image_path, np.ones((4, 4), dtype=np.uint8))

    queue = ImageQueue()
    first_summary = queue.add_images([image_path])
    original_row = queue.rows[0]
    second_summary = queue.add_images([image_path])

    assert first_summary.added_count == 1
    assert second_summary.added_count == 0
    assert second_summary.skipped_count == 0
    assert len(queue.rows) == 1
    assert queue.rows[0] is original_row


def test_set_group_applies_trimmed_name_to_selected_rows(tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    third_path = tmp_path / "third.tif"
    for image_path in (first_path, second_path, third_path):
        tifffile.imwrite(image_path, np.ones((4, 4), dtype=np.uint8))

    queue = ImageQueue()
    queue.add_images([first_path, second_path, third_path])

    assert queue.set_group([0, 2], "  Process A  ") is True

    assert queue.rows[0].group == "Process A"
    assert queue.rows[1].group == "Default"
    assert queue.rows[2].group == "Process A"


def test_set_group_rejects_empty_name_without_changing_rows(tmp_path):
    image_path = tmp_path / "stem_zc.tif"
    tifffile.imwrite(image_path, np.ones((4, 4), dtype=np.uint8))

    queue = ImageQueue()
    queue.add_images([image_path])
    queue.set_group([0], "A")

    assert queue.set_group([0], "   ") is False
    assert queue.rows[0].group == "A"


def test_scale_uses_metadata_and_blocks_manual_override(tmp_path):
    image_path = tmp_path / "metadata_scale.tif"
    image = np.ones((4, 4), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image, metadata_nm_per_px=0.8)

    assert queue.resolve_scale(0) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )
    assert queue.set_manual_scale(0, "0.5") is False
    assert queue.resolve_scale(0) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )


def test_manual_scale_accepts_blank_positive_values_and_preserves_valid_state(
    tmp_path,
):
    image_path = tmp_path / "manual_scale.tif"
    second_path = tmp_path / "second_manual_scale.tif"
    image = np.ones((4, 4), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.add_image_data(second_path, image)

    assert queue.resolve_scale(0) == ScaleResolution(source="px", nm_per_px=None)
    assert queue.set_manual_scale(0, "0.25") is True
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.resolve_scale(1) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )

    assert queue.set_manual_scale(0, "0") is False
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.rows[0].scale_error == "Enter a positive nm / pixel value."

    assert queue.set_manual_scale(0, "not numeric") is False
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )

    assert queue.set_manual_scale(0, "   ") is True
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.rows[0].scale_error == ""


def test_manual_scale_uses_default_until_single_image_override(tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    metadata_path = tmp_path / "metadata.tif"
    image = np.ones((4, 4), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(first_path, image)
    queue.add_image_data(second_path, image)
    queue.add_image_data(metadata_path, image, metadata_nm_per_px=0.8)

    assert queue.set_manual_scale(0, "0.25") is True
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.resolve_scale(1) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.resolve_scale(2) == ScaleResolution(
        source="metadata", nm_per_px=0.8
    )

    assert queue.set_manual_scale(1, "0.5") is True
    assert queue.resolve_scale(0) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )
    assert queue.resolve_scale(1) == ScaleResolution(
        source="manual_override", nm_per_px=0.5
    )

    assert queue.set_manual_scale(1, "   ") is True
    assert queue.resolve_scale(1) == ScaleResolution(
        source="manual_default", nm_per_px=0.25
    )


def test_roi_is_clamped_and_clears_stale_measurement_state(tmp_path):
    image_path = tmp_path / "roi.tif"
    image = np.ones((10, 20), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.record_measurement_result(0, {"measurements": [1]})

    assert queue.set_roi(0, RectRoi(x=-5, y=2, width=30, height=20)) is True

    row = queue.rows[0]
    assert row.roi.rectangles == (RectRoi(x=0, y=2, width=20, height=8),)
    assert row.roi_status == "Custom ROI"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.clear_roi(0) is True

    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None


def test_setting_roi_appends_rectangle_shapes_and_clears_stale_measurement_state(
    tmp_path,
):
    image_path = tmp_path / "multi_roi.tif"
    image = np.ones((40, 60), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.record_measurement_result(0, {"measurements": [1]})

    assert queue.set_roi(0, RectRoi(x=2, y=3, width=10, height=12)) is True
    assert queue.set_roi(0, RectRoi(x=30, y=20, width=15, height=10)) is True

    row = queue.rows[0]
    assert row.roi.rectangles == (
        RectRoi(x=2, y=3, width=10, height=12),
        RectRoi(x=30, y=20, width=15, height=10),
    )
    assert row.roi_status == "Custom ROI"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None


def test_undo_roi_removes_latest_rectangle_shape_and_returns_to_full_image(
    tmp_path,
):
    image_path = tmp_path / "undo_roi.tif"
    image = np.ones((40, 60), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.set_roi(0, RectRoi(x=2, y=3, width=10, height=12))
    queue.set_roi(0, RectRoi(x=30, y=20, width=15, height=10))
    queue.record_measurement_result(0, {"measurements": [1]})

    assert queue.undo_roi(0) is True

    row = queue.rows[0]
    assert row.roi.rectangles == (RectRoi(x=2, y=3, width=10, height=12),)
    assert row.roi_status == "Custom ROI"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.undo_roi(0) is True

    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.clear_roi(0) is True

    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None


def test_polygon_roi_shape_can_be_added_undone_and_cleared(tmp_path):
    image_path = tmp_path / "polygon_roi.tif"
    image = np.ones((40, 60), dtype=np.uint8)
    polygon = PolygonRoi(points=((5, 5), (35, 5), (20, 30)))

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.record_measurement_result(0, {"measurements": [1]})

    assert queue.add_polygon_roi(0, polygon) is True

    row = queue.rows[0]
    assert row.roi.polygons == (polygon,)
    assert row.roi_status == "Custom ROI"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.undo_roi(0) is True

    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.add_polygon_roi(0, polygon)
    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.clear_roi(0) is True

    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None


def test_undo_roi_removes_latest_completed_shape_across_rectangle_and_polygon(
    tmp_path,
):
    image_path = tmp_path / "mixed_roi.tif"
    image = np.ones((40, 60), dtype=np.uint8)
    rectangle = RectRoi(x=2, y=3, width=10, height=12)
    polygon = PolygonRoi(points=((5, 5), (35, 5), (20, 30)))

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.set_roi(0, rectangle)
    queue.add_polygon_roi(0, polygon)

    assert queue.undo_roi(0) is True
    row = queue.rows[0]
    assert row.roi.rectangles == (rectangle,)
    assert row.roi.polygons == ()
    assert row.roi_status == "Custom ROI"

    assert queue.undo_roi(0) is True
    row = queue.rows[0]
    assert row.roi.is_empty
    assert row.roi_status == "Full image"
