import numpy as np
import tifffile
from PySide6.QtCore import QItemSelectionModel

from measurer.app import create_window
from measurer.synthetic import SingleMetalIslandSpec, create_single_metal_island_image


def test_app_window_opens_with_empty_queue(qapp):
    window = create_window()

    assert window.windowTitle() == "Measurer"
    assert window.add_images_button.text() == "Add Images"
    assert window.file_table.rowCount() == 0
    assert "No images added" in window.status_label.text()


def test_app_adds_tiff_to_queue_and_original_preview(qapp, tmp_path):
    image_path = tmp_path / "stem_zc.tif"
    tifffile.imwrite(image_path, np.ones((6, 5), dtype=np.uint8) * 120)
    window = create_window()

    summary = window.add_image_paths([image_path])

    assert summary.added_count == 1
    assert window.file_table.rowCount() == 1
    assert window.file_table.item(0, 1).text() == "stem_zc.tif"
    assert window.file_table.item(0, 2).text() == "Default"
    assert window.file_table.item(0, 3).text() == "Full image"
    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(0, 5).text() == "Not exported"
    assert window.status_label.text() == "Added 1 image."
    assert window.image_label.pixmap() is not None
    assert not window.image_label.pixmap().isNull()


def test_app_shows_selected_image_in_original_preview(qapp, tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    tifffile.imwrite(first_path, np.ones((6, 5), dtype=np.uint8))
    tifffile.imwrite(second_path, np.ones((9, 7), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([first_path, second_path])
    first_size = window.image_label.pixmap().size()
    window.file_table.setCurrentCell(1, 1)
    qapp.processEvents()

    selected_size = window.image_label.pixmap().size()
    assert first_size.width() == 5
    assert first_size.height() == 6
    assert selected_size.width() == 7
    assert selected_size.height() == 9


def test_app_applies_group_and_manual_scale_to_selected_rows(qapp, tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    tifffile.imwrite(first_path, np.ones((6, 5), dtype=np.uint8))
    tifffile.imwrite(second_path, np.ones((9, 7), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([first_path, second_path])
    selection_model = window.file_table.selectionModel()
    selection_flags = (
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows
    )
    selection_model.select(window.file_table.model().index(0, 0), selection_flags)
    selection_model.select(window.file_table.model().index(1, 0), selection_flags)
    window.group_input.setText("  Process A  ")
    window.set_group_button.click()

    assert window.file_table.item(0, 2).text() == "Process A"
    assert window.file_table.item(1, 2).text() == "Process A"

    window.file_table.setCurrentCell(0, 1)
    window.scale_input.setText("0.25")
    window.scale_input.editingFinished.emit()
    assert window.queue.resolve_scale(0).source == "manual"
    assert window.queue.resolve_scale(0).nm_per_px == 0.25

    window.scale_input.setText("-1")
    window.scale_input.editingFinished.emit()
    assert window.queue.resolve_scale(0).nm_per_px == 0.25
    assert "positive" in window.scale_error_label.text()


def test_app_sets_and_clears_roi_for_selected_image(qapp, tmp_path):
    image_path = tmp_path / "roi.tif"
    tifffile.imwrite(image_path, np.ones((10, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])
    window.queue.record_measurement_result(0, {"measurements": [1]})
    window.set_selected_roi(-5, 2, 30, 20)

    assert window.file_table.item(0, 3).text() == "Custom ROI"
    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(0, 5).text() == "Not exported"

    window.clear_roi_button.click()

    assert window.file_table.item(0, 3).text() == "Full image"
    assert window.queue.rows[0].roi is None


def test_app_measure_current_updates_only_selected_image_and_shows_result_view(
    qapp, tmp_path
):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
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
    tifffile.imwrite(first_path, np.ones((128, 128), dtype=np.uint8) * 20)
    tifffile.imwrite(second_path, image)
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setCurrentCell(1, 1)
    window.measure_current_button.click()

    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(1, 4).text() == "Measured"
    assert window.file_table.item(1, 5).text() == "Not exported"
    assert window.current_view_mode == "Result View"
    assert "TCD 32.0 px" in window.result_values_label.text()
    assert "BCD 48.0 px" in window.result_values_label.text()
    assert "Height 60.0 px" in window.result_values_label.text()


def test_app_failed_measure_current_stays_on_original_view_with_reason(
    qapp, tmp_path
):
    image_path = tmp_path / "no_candidates.tif"
    tifffile.imwrite(image_path, np.ones((128, 128), dtype=np.uint8) * 20)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()

    assert window.file_table.item(0, 4).text() == "Failed"
    assert window.current_view_mode == "Original View"
    assert window.result_values_label.text() == ""
    assert window.status_label.text() == "No metal candidates"


def test_app_debug_view_shows_candidate_filtering_diagnostics(qapp, tmp_path):
    image_path = tmp_path / "contamination.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.debug_view_button.click()

    assert window.current_view_mode == "Debug View"
    assert window.image_label.pixmap() is not None
    assert "Kept candidates: 1" in window.result_values_label.text()
    assert "Excluded small components: 1" in window.result_values_label.text()
    assert "Excluded boundary-touch components: 0" in window.result_values_label.text()


def test_app_debug_view_shows_refinement_diagnostics(qapp, tmp_path):
    image_path = tmp_path / "fallback_boundary.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.set_selected_roi(37, 16, 54, 88)
    window.measure_current_button.click()
    window.debug_view_button.click()

    assert window.current_view_mode == "Debug View"
    assert window.image_label.pixmap() is not None
    assert "Refined points: 0" in window.result_values_label.text()
    assert "Fallback points:" in window.result_values_label.text()
    assert "Fallback ratio: 100.0%" in window.result_values_label.text()


def test_app_debug_view_shows_boundary_touch_diagnostics_after_failure(
    qapp, tmp_path
):
    image_path = tmp_path / "boundary_touch.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.debug_view_button.click()

    assert window.file_table.item(0, 4).text() == "Failed"
    assert window.current_view_mode == "Debug View"
    assert "Kept candidates: 0" in window.result_values_label.text()
    assert "Excluded boundary-touch components: 1" in window.result_values_label.text()
