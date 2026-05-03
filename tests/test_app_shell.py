import numpy as np
import tifffile
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtGui import QColor

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


def test_app_result_view_shows_multiple_metal_islands_and_space_measurements(
    qapp, tmp_path
):
    image_path = tmp_path / "multi_island.tif"
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
    image[right_image == 220] = 220
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()

    assert window.file_table.item(0, 4).text() == "Measured"
    assert "M001 TCD 32.0 px" in window.result_values_label.text()
    assert "M002 BCD 42.0 px" in window.result_values_label.text()
    assert "M001-M002 Horizontal Space 44.0 px" in window.result_values_label.text()


def test_app_result_view_draws_measurement_type_colors(qapp, tmp_path):
    image_path = tmp_path / "result_colors.tif"
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
    for center_x, top_y in [(150, 24), (60, 120), (150, 120)]:
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()

    assert "Horizontal Space" in window.result_values_label.text()
    assert "Vertical Space" in window.result_values_label.text()
    result_image = window.image_label.pixmap().toImage()
    expected_colors = [
        QColor(64, 196, 255),
        QColor(255, 183, 77),
        QColor(255, 210, 64),
        QColor(186, 104, 200),
        QColor(129, 199, 132),
    ]
    for color in expected_colors:
        assert _image_contains_color(result_image, color)


def test_app_result_view_refreshes_values_when_manual_scale_changes(qapp, tmp_path):
    image_path = tmp_path / "scaled_result.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    assert "TCD 32.0 px" in window.result_values_label.text()

    window.scale_input.setText("0.5")
    window.scale_input.editingFinished.emit()

    assert window.current_view_mode == "Result View"
    assert window.file_table.item(0, 4).text() == "Measured"
    assert "TCD 16.0 nm" in window.result_values_label.text()
    assert "BCD 24.0 nm" in window.result_values_label.text()
    assert "Height 30.0 nm" in window.result_values_label.text()


def test_app_box_plot_preview_summarizes_measured_results_by_group(qapp, tmp_path):
    image_path = tmp_path / "box_plot_source.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.group_input.setText("Process A")
    window.set_group_button.click()
    window.measure_current_button.click()
    window.box_plot_view_button.click()

    assert window.current_view_mode == "Box Plot"
    assert window.image_label.pixmap() is not None
    assert not window.image_label.pixmap().isNull()
    assert "Box Plot" in window.result_values_label.text()
    assert "Process A" in window.result_values_label.text()
    assert "TCD" in window.result_values_label.text()
    assert "BCD" in window.result_values_label.text()
    assert "Height" in window.result_values_label.text()
    assert "3 measurements" in window.result_values_label.text()
    assert "px" in window.result_values_label.text()


def test_app_box_plot_refreshes_when_group_changes_without_remeasure(qapp, tmp_path):
    image_path = tmp_path / "box_plot_group_refresh.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.group_input.setText("Process A")
    window.set_group_button.click()
    window.measure_current_button.click()
    window.box_plot_view_button.click()
    assert "Process A" in window.result_values_label.text()

    window.group_input.setText("Process B")
    window.set_group_button.click()

    assert window.current_view_mode == "Box Plot"
    assert "Process B" in window.result_values_label.text()
    assert "Process A" not in window.result_values_label.text()
    assert window.file_table.item(0, 4).text() == "Measured"


def test_app_box_plot_refreshes_when_manual_scale_changes_without_remeasure(
    qapp, tmp_path
):
    image_path = tmp_path / "box_plot_scale_refresh.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.box_plot_view_button.click()
    assert "Unit: px" in window.result_values_label.text()

    window.scale_input.setText("0.5")
    window.scale_input.editingFinished.emit()

    assert window.current_view_mode == "Box Plot"
    assert "Unit: nm" in window.result_values_label.text()
    assert "3 measurements" in window.result_values_label.text()
    assert window.file_table.item(0, 4).text() == "Measured"


def test_app_box_plot_warns_instead_of_drawing_mixed_units(qapp, tmp_path):
    first_path = tmp_path / "box_plot_nm.tif"
    second_path = tmp_path / "box_plot_px.tif"
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
    tifffile.imwrite(first_path, image)
    tifffile.imwrite(second_path, image)
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setCurrentCell(0, 1)
    window.scale_input.setText("0.5")
    window.scale_input.editingFinished.emit()
    window.measure_current_button.click()
    window.file_table.setCurrentCell(1, 1)
    window.measure_current_button.click()
    window.box_plot_view_button.click()

    assert window.current_view_mode == "Box Plot"
    assert "cannot mix nm and px" in window.result_values_label.text()


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


def test_app_export_blocks_when_no_images_are_measured(qapp, tmp_path):
    image_path = tmp_path / "pending_export.tif"
    tifffile.imwrite(image_path, np.ones((128, 128), dtype=np.uint8) * 20)
    window = create_window()

    window.add_image_paths([image_path])
    window.export_button.click()

    assert window.status_label.text() == "No measured images to export."
    assert not (tmp_path / "measured_image").exists()
    assert not (tmp_path / "debug_image").exists()
    assert window.file_table.item(0, 5).text() == "Not exported"


def test_app_export_writes_measured_images_and_updates_status(qapp, tmp_path):
    image_path = tmp_path / "gui_export.tif"
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
    tifffile.imwrite(image_path, image)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.export_button.click()

    assert window.file_table.item(0, 5).text() == "Exported"
    assert window.status_label.text() == "Exported 1 measured image."
    assert (tmp_path / "measured_image" / "gui_export_result.png").is_file()
    assert (tmp_path / "debug_image" / "gui_export_debug.png").is_file()
    assert (tmp_path / "measured_image" / "measurements.xlsx").is_file()


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


def _image_contains_color(image, expected_color: QColor) -> bool:
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if (
                color.red() == expected_color.red()
                and color.green() == expected_color.green()
                and color.blue() == expected_color.blue()
            ):
                return True
    return False
