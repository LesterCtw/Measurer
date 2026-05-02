import numpy as np
import tifffile

from measurer.image_queue import ImageQueue


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
