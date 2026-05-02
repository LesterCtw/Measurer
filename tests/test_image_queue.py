import numpy as np
import tifffile

from measurer.image_queue import ImageQueue, RectRoi, ScaleResolution


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
    image = np.ones((4, 4), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)

    assert queue.resolve_scale(0) == ScaleResolution(source="px", nm_per_px=None)
    assert queue.set_manual_scale(0, "0.25") is True
    assert queue.resolve_scale(0) == ScaleResolution(source="manual", nm_per_px=0.25)

    assert queue.set_manual_scale(0, "0") is False
    assert queue.resolve_scale(0) == ScaleResolution(source="manual", nm_per_px=0.25)
    assert queue.rows[0].scale_error == "Enter a positive nm / pixel value."

    assert queue.set_manual_scale(0, "not numeric") is False
    assert queue.resolve_scale(0) == ScaleResolution(source="manual", nm_per_px=0.25)

    assert queue.set_manual_scale(0, "   ") is True
    assert queue.resolve_scale(0) == ScaleResolution(source="px", nm_per_px=None)
    assert queue.rows[0].scale_error == ""


def test_roi_is_clamped_and_clears_stale_measurement_state(tmp_path):
    image_path = tmp_path / "roi.tif"
    image = np.ones((10, 20), dtype=np.uint8)

    queue = ImageQueue()
    queue.add_image_data(image_path, image)
    queue.record_measurement_result(0, {"measurements": [1]})

    assert queue.set_roi(0, RectRoi(x=-5, y=2, width=30, height=20)) is True

    row = queue.rows[0]
    assert row.roi == RectRoi(x=0, y=2, width=20, height=8)
    assert row.roi_status == "Custom ROI"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None

    queue.record_measurement_result(0, {"measurements": [1]})
    assert queue.clear_roi(0) is True

    row = queue.rows[0]
    assert row.roi is None
    assert row.roi_status == "Full image"
    assert row.measure_status == "Pending"
    assert row.export_status == "Not exported"
    assert row.measurement_results is None
