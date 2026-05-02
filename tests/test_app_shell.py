import numpy as np
import tifffile
from PySide6.QtCore import QItemSelectionModel

from measurer.app import create_window


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
