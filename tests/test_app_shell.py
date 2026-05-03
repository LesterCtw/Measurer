import numpy as np
import tifffile
from PySide6.QtCore import QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
)

import measurer.app as app_module
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
    assert window.file_table.item(0, 1).text() == ""
    assert window.file_table.item(0, 2).text() == "Default"
    assert _queue_file_text(window, 0) == ("stem_zc.tif", "Default")
    assert _queue_status_text(window, 0) == ("Full image · Pending", "Not exported")
    assert window.file_table.item(0, 3).text() == ""
    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(0, 5).text() == "Not exported"
    assert window.status_label.text() == "Added 1 image."
    assert window.image_label.pixmap() is not None
    assert not window.image_label.pixmap().isNull()


def test_app_add_images_dialog_allows_dm3_selection(qapp, monkeypatch):
    captured_filters = []

    def fake_get_open_file_names(parent, title, directory, file_filter):
        captured_filters.append(file_filter)
        return [], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", fake_get_open_file_names)
    window = create_window()

    window.add_images_button.click()

    assert captured_filters == ["STEM ZC Images (*.tif *.tiff *.dm3)"]


def test_app_measures_dm3_without_metadata_in_px(qapp, monkeypatch, tmp_path):
    image_path = tmp_path / "pixel_fallback.dm3"
    image_path.write_bytes(b"fake dm3")
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

    def fake_file_reader(filename):
        return [{"data": image, "axes": []}]

    monkeypatch.setattr(
        "rsciio.digitalmicrograph.file_reader",
        fake_file_reader,
    )
    window = create_window()

    summary = window.add_image_paths([image_path])
    window.measure_current_button.click()

    assert summary.added_count == 1
    assert window.file_table.item(0, 4).text() == "Measured"
    assert "TCD: 32.0 px (n=1)" in window.result_values_label.text()


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


def test_app_returns_to_result_view_for_already_measured_image(qapp, tmp_path):
    first_path = tmp_path / "first_measured.tif"
    second_path = tmp_path / "second_pending.tif"
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
    tifffile.imwrite(second_path, np.ones((128, 128), dtype=np.uint8) * 20)
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.measure_current_button.click()
    window.file_table.setCurrentCell(1, 1)
    window.file_table.setCurrentCell(0, 1)

    assert window.current_view_mode == "Result View"
    assert "TCD: 32.0 px (n=1)" in window.result_values_label.text()


def test_original_preview_size_hint_does_not_follow_large_image(qapp, tmp_path):
    image_path = tmp_path / "large_preview.tif"
    tifffile.imwrite(image_path, np.ones((1800, 2400), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])
    window.original_view_button.click()

    hint = window.image_label.sizeHint()
    assert hint.width() <= 900
    assert hint.height() <= 700


def test_roi_drag_preview_maps_fitted_canvas_to_image_coordinates(qapp, tmp_path):
    image_path = tmp_path / "fit_roi.tif"
    tifffile.imwrite(image_path, np.ones((100, 200), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])
    window.image_label.setFixedSize(800, 400)
    qapp.processEvents()

    QTest.mousePress(window.image_label, Qt.MouseButton.LeftButton, pos=QPoint(200, 100))
    QTest.mouseMove(window.image_label, QPoint(600, 300))

    preview = window.image_label.roi_preview()
    assert preview is not None
    assert preview.x == 50
    assert preview.y == 25
    assert preview.width == 100
    assert preview.height == 50

    QTest.mouseRelease(
        window.image_label,
        Qt.MouseButton.LeftButton,
        pos=QPoint(600, 300),
    )

    assert window.queue.rows[0].roi is not None
    assert window.queue.rows[0].roi.x == 50
    assert window.queue.rows[0].roi.y == 25
    assert window.queue.rows[0].roi.width == 100
    assert window.queue.rows[0].roi.height == 50
    assert _queue_status_text(window, 0)[0] == "Custom ROI · Pending"


def test_queue_status_cell_does_not_duplicate_status_text(qapp, tmp_path):
    image_path = tmp_path / "status_cell.tif"
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
    window.set_selected_roi(10, 10, 100, 100)
    window.measure_current_button.click()

    assert window.file_table.item(0, 3).text() == ""
    assert _queue_status_text(window, 0) == (
        "Custom ROI · Measured",
        "Not exported",
    )


def test_roi_outline_does_not_fill_the_selected_region(qapp, tmp_path):
    image_path = tmp_path / "roi_outline.tif"
    tifffile.imwrite(image_path, np.ones((100, 200), dtype=np.uint8) * 120)
    window = create_window()

    window.add_image_paths([image_path])
    window.image_label.setFixedSize(200, 100)
    window.set_selected_roi(50, 25, 100, 50)
    qapp.processEvents()

    rendered = _render_widget(window.image_label)
    center_color = rendered.pixelColor(100, 50)
    assert abs(center_color.red() - 120) <= 1
    assert abs(center_color.green() - 120) <= 1
    assert abs(center_color.blue() - 120) <= 1


def test_file_queue_fits_sidebar_without_horizontal_scroll(qapp, tmp_path):
    first_path = tmp_path / "first_measurement_source.tif"
    second_path = tmp_path / "second_measurement_source.tif"
    tifffile.imwrite(first_path, np.ones((20, 20), dtype=np.uint8))
    tifffile.imwrite(second_path, np.ones((20, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setFixedWidth(360)
    window.show()
    qapp.processEvents()

    visible_width = sum(
        window.file_table.columnWidth(column)
        for column in range(window.file_table.columnCount())
        if not window.file_table.isColumnHidden(column)
    )
    assert window.file_table.isColumnHidden(0)
    assert window.file_table.horizontalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert visible_width <= window.file_table.viewport().width() + 2


def test_file_queue_uses_single_image_cell_and_hides_detail_columns(qapp, tmp_path):
    image_path = tmp_path / "very_long_measurement_source_name_for_review.tif"
    tifffile.imwrite(image_path, np.ones((20, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])

    assert window.file_table.isColumnHidden(2)
    assert window.file_table.isColumnHidden(3)
    assert window.file_table.item(0, 1).text() == ""
    assert _queue_file_text(window, 0) == (image_path.name, "Default")
    assert _queue_status_text(window, 0) == ("Full image · Pending", "Not exported")


def test_file_queue_does_not_allow_inline_editing(qapp, tmp_path):
    image_path = tmp_path / "readonly_queue.tif"
    tifffile.imwrite(image_path, np.ones((20, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])

    assert window.file_table.editTriggers() == (
        QAbstractItemView.EditTrigger.NoEditTriggers
    )
    assert not window.file_table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable
    assert not window.file_table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable


def test_group_controls_are_directly_above_file_queue(qapp):
    window = create_window()

    sidebar_layout = window.group_controls_panel.parentWidget().layout()

    assert isinstance(window.group_controls_panel.layout(), QHBoxLayout)
    assert sidebar_layout.indexOf(window.group_controls_panel) == (
        sidebar_layout.indexOf(window.file_table) - 1
    )


def test_same_group_uses_same_queue_badge_color(qapp, tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    tifffile.imwrite(first_path, np.ones((20, 20), dtype=np.uint8))
    tifffile.imwrite(second_path, np.ones((20, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([first_path, second_path])
    selection_model = window.file_table.selectionModel()
    selection_flags = (
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows
    )
    selection_model.select(window.file_table.model().index(0, 0), selection_flags)
    selection_model.select(window.file_table.model().index(1, 0), selection_flags)
    window.group_input.setText("Process A")
    window.set_group_button.click()

    assert _queue_file_text(window, 0)[1] == "Process A"
    assert _queue_file_text(window, 1)[1] == "Process A"
    assert _queue_group_badge_style(window, 0) == _queue_group_badge_style(window, 1)


def test_file_queue_normal_click_selects_only_one_row(qapp, tmp_path):
    first_path = tmp_path / "first.tif"
    second_path = tmp_path / "second.tif"
    tifffile.imwrite(first_path, np.ones((20, 20), dtype=np.uint8))
    tifffile.imwrite(second_path, np.ones((20, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setFixedSize(420, 180)
    window.show()
    qapp.processEvents()

    first_center = window.file_table.visualItemRect(
        window.file_table.item(0, 1)
    ).center()
    second_center = window.file_table.visualItemRect(
        window.file_table.item(1, 1)
    ).center()
    QTest.mouseClick(
        window.file_table.viewport(), Qt.MouseButton.LeftButton, pos=first_center
    )
    QTest.mouseClick(
        window.file_table.viewport(), Qt.MouseButton.LeftButton, pos=second_center
    )

    assert window.file_table.selectionMode() == (
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    assert sorted(
        index.row() for index in window.file_table.selectionModel().selectedRows()
    ) == [1]


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
    assert window.queue.resolve_scale(0).source == "manual_default"
    assert window.queue.resolve_scale(0).nm_per_px == 0.25
    assert window.queue.resolve_scale(1).source == "manual_default"
    assert window.queue.resolve_scale(1).nm_per_px == 0.25

    window.file_table.setCurrentCell(1, 1)
    window.scale_input.setText("0.5")
    window.scale_input.editingFinished.emit()
    assert window.queue.resolve_scale(1).source == "manual_override"
    assert window.queue.resolve_scale(1).nm_per_px == 0.5

    window.scale_input.setText("-1")
    window.scale_input.editingFinished.emit()
    assert window.queue.resolve_scale(1).nm_per_px == 0.5
    assert "positive" in window.scale_error_label.text()


def test_app_sets_and_clears_roi_for_selected_image(qapp, tmp_path):
    image_path = tmp_path / "roi.tif"
    tifffile.imwrite(image_path, np.ones((10, 20), dtype=np.uint8))
    window = create_window()

    window.add_image_paths([image_path])
    window.queue.record_measurement_result(0, {"measurements": [1]})
    window.set_selected_roi(-5, 2, 30, 20)

    assert _queue_status_text(window, 0)[0] == "Custom ROI · Pending"
    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(0, 5).text() == "Not exported"

    window.clear_roi_button.click()

    assert _queue_status_text(window, 0)[0] == "Full image · Pending"
    assert window.queue.rows[0].roi is None


def test_app_measure_current_keeps_too_small_roi_pending(qapp, tmp_path):
    image_path = tmp_path / "tiny_roi.tif"
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
    window.set_selected_roi(10, 10, 5, 5)
    window.measure_current_button.click()

    assert _queue_status_text(window, 0)[0] == "Custom ROI · Pending"
    assert window.file_table.item(0, 4).text() == "Pending"
    assert window.file_table.item(0, 5).text() == "Not exported"
    assert window.status_label.text() == "ROI is too small."
    assert window.queue.rows[0].measurement_results is None


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
    assert "TCD: 32.0 px (n=1)" in window.result_values_label.text()
    assert "BCD: 48.0 px (n=1)" in window.result_values_label.text()
    assert "Height: 60.0 px (n=1)" in window.result_values_label.text()


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
    assert "TCD: 30.0-32.0 px (n=2)" in window.result_values_label.text()
    assert "BCD: 42.0-48.0 px (n=2)" in window.result_values_label.text()
    assert "Horizontal Space: 44.0 px (n=1)" in window.result_values_label.text()


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
    window.image_label.setFixedSize(480, 440)
    qapp.processEvents()

    assert "Horizontal Space" in window.result_values_label.text()
    assert "Vertical Space" in window.result_values_label.text()
    result_image = _render_widget(window.image_label)
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
    assert "TCD: 32.0 px (n=1)" in window.result_values_label.text()

    window.scale_input.setText("0.5")
    window.scale_input.editingFinished.emit()

    assert window.current_view_mode == "Result View"
    assert window.file_table.item(0, 4).text() == "Measured"
    assert "TCD: 16.0 nm (n=1)" in window.result_values_label.text()
    assert "BCD: 24.0 nm (n=1)" in window.result_values_label.text()
    assert "Height: 30.0 nm (n=1)" in window.result_values_label.text()


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
    rendered = _render_widget(window.image_label)
    assert rendered.width() > 0
    assert rendered.height() > 0
    assert "Box Plot" in window.result_values_label.text()
    assert "Process A" in window.result_values_label.text()
    assert "TCD" in window.result_values_label.text()
    assert "BCD" in window.result_values_label.text()
    assert "Height" in window.result_values_label.text()
    assert "3 measurements" in window.result_values_label.text()
    assert "px" in window.result_values_label.text()


def test_app_box_plot_filters_measurement_types_without_remeasure(qapp, tmp_path):
    image_path = tmp_path / "box_plot_filter_source.tif"
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

    checkboxes = {
        checkbox.text(): checkbox for checkbox in window.findChildren(QCheckBox)
    }
    assert set(checkboxes) >= {
        "All",
        "TCD",
        "BCD",
        "Height",
        "Horizontal Space",
        "Vertical Space",
    }
    assert checkboxes["All"].isChecked()
    for measurement_type in app_module.MEASUREMENT_TYPE_ORDER:
        assert checkboxes[measurement_type].isChecked()
    assert "3 measurements" in window.result_values_label.text()
    assert "Height" in window.result_values_label.text()

    checkboxes["Height"].click()

    assert window.current_view_mode == "Box Plot"
    assert window.file_table.item(0, 4).text() == "Measured"
    assert not checkboxes["All"].isChecked()
    assert "2 measurements" in window.result_values_label.text()
    assert "TCD" in window.result_values_label.text()
    assert "BCD" in window.result_values_label.text()
    assert "Height" not in window.result_values_label.text()

    checkboxes["Height"].click()

    assert window.file_table.item(0, 4).text() == "Measured"
    assert checkboxes["All"].isChecked()
    assert "3 measurements" in window.result_values_label.text()
    assert "Height" in window.result_values_label.text()


def test_app_box_plot_all_filter_toggles_all_measurement_types(qapp, tmp_path):
    image_path = tmp_path / "box_plot_all_filter_source.tif"
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

    checkboxes = {
        checkbox.text(): checkbox for checkbox in window.findChildren(QCheckBox)
    }
    checkboxes["All"].click()

    assert not checkboxes["All"].isChecked()
    for measurement_type in app_module.MEASUREMENT_TYPE_ORDER:
        assert not checkboxes[measurement_type].isChecked()
    assert "no selected measurement types" in window.result_values_label.text()

    checkboxes["All"].click()

    assert checkboxes["All"].isChecked()
    for measurement_type in app_module.MEASUREMENT_TYPE_ORDER:
        assert checkboxes[measurement_type].isChecked()
    assert "3 measurements" in window.result_values_label.text()


def test_app_box_plot_shows_empty_state_when_all_measurement_types_are_hidden(
    qapp, tmp_path
):
    image_path = tmp_path / "box_plot_empty_filter_source.tif"
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

    checkboxes = {
        checkbox.text(): checkbox for checkbox in window.findChildren(QCheckBox)
    }
    for measurement_type in app_module.MEASUREMENT_TYPE_ORDER:
        checkboxes[measurement_type].click()

    rendered = _render_widget(window.image_label)
    assert rendered.width() > 0
    assert rendered.height() > 0
    assert "no selected measurement types" in window.result_values_label.text()
    assert window.file_table.item(0, 4).text() == "Measured"


def test_box_plot_buckets_alternate_groups_within_each_measurement_type():
    points = [
        app_module.BoxPlotPoint("LF", "BCD", 4.0, "px"),
        app_module.BoxPlotPoint("EF", "BCD", 3.0, "px"),
        app_module.BoxPlotPoint("LF", "TCD", 2.0, "px"),
        app_module.BoxPlotPoint("EF", "TCD", 1.0, "px"),
    ]

    buckets = app_module._box_plot_buckets(points)

    assert [key for key, _values in buckets] == [
        ("EF", "TCD"),
        ("LF", "TCD"),
        ("EF", "BCD"),
        ("LF", "BCD"),
    ]


def test_box_plot_ticks_include_range_endpoints():
    ticks = app_module._box_plot_ticks(26.0, 60.0)

    assert ticks == [26.0, 34.5, 43.0, 51.5, 60.0]


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

    window.queue.add_image_data(first_path, image, metadata_nm_per_px=0.5)
    window.queue.add_image_data(second_path, image)
    window._refresh_file_table()
    window.file_table.setCurrentCell(0, 1)
    window._select_image(0)
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


def test_app_multi_source_export_canceling_output_folder_writes_nothing(
    qapp, tmp_path, monkeypatch
):
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    first_folder.mkdir()
    second_folder.mkdir()
    first_path = first_folder / "first.tif"
    second_path = second_folder / "second.tif"
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
    folder_picker_calls = []

    def cancel_output_folder_picker(*args):
        folder_picker_calls.append(args)
        return ""

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", cancel_output_folder_picker
    )
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setCurrentCell(0, 1)
    window.measure_current_button.click()
    window.file_table.setCurrentCell(1, 1)
    window.measure_current_button.click()
    window.export_button.click()

    assert len(folder_picker_calls) == 1
    assert window.status_label.text() == "Choose an output folder for multi-source export."
    assert window.file_table.item(0, 5).text() == "Not exported"
    assert window.file_table.item(1, 5).text() == "Not exported"
    assert not (tmp_path / "measured_image").exists()
    assert not (tmp_path / "debug_image").exists()


def test_app_multi_source_export_uses_chosen_output_folder(
    qapp, tmp_path, monkeypatch
):
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    output_folder = tmp_path / "export"
    first_folder.mkdir()
    second_folder.mkdir()
    first_path = first_folder / "first.tif"
    second_path = second_folder / "second.tif"
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
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: str(output_folder)
    )
    window = create_window()

    window.add_image_paths([first_path, second_path])
    window.file_table.setCurrentCell(0, 1)
    window.measure_current_button.click()
    window.file_table.setCurrentCell(1, 1)
    window.measure_current_button.click()
    window.export_button.click()

    assert window.file_table.item(0, 5).text() == "Exported"
    assert window.file_table.item(1, 5).text() == "Exported"
    assert window.status_label.text() == "Exported 2 measured images."
    assert (output_folder / "measured_image" / "first_result.png").is_file()
    assert (output_folder / "measured_image" / "second_result.png").is_file()
    assert (output_folder / "debug_image" / "first_debug.png").is_file()
    assert (output_folder / "debug_image" / "second_debug.png").is_file()
    assert (output_folder / "measured_image" / "measurements.xlsx").is_file()


def test_app_overwrite_dialog_cancel_aborts_export(qapp, tmp_path, monkeypatch):
    image_path = tmp_path / "existing.tif"
    measured_folder = tmp_path / "measured_image"
    debug_folder = tmp_path / "debug_image"
    measured_folder.mkdir()
    debug_folder.mkdir()
    existing_result = measured_folder / "existing_result.png"
    existing_debug = debug_folder / "existing_debug.png"
    existing_workbook = measured_folder / "measurements.xlsx"
    existing_result.write_text("old result")
    existing_debug.write_text("old debug")
    existing_workbook.write_text("old workbook")
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

    class FakeMessageBox:
        instances = []

        class ButtonRole:
            RejectRole = "reject"
            AcceptRole = "accept"

        def __init__(self, parent=None):
            self.parent = parent
            self.window_title = ""
            self.text = ""
            self.buttons = []
            self.default_button = None
            self._clicked_button = None
            FakeMessageBox.instances.append(self)

        def setWindowTitle(self, title):
            self.window_title = title

        def setText(self, text):
            self.text = text

        def addButton(self, text, role):
            self.buttons.append((text, role))
            return text

        def setDefaultButton(self, button):
            self.default_button = button

        def exec(self):
            self._clicked_button = "Cancel"
            return 0

        def clickedButton(self):
            return self._clicked_button

    monkeypatch.setattr(app_module, "QMessageBox", FakeMessageBox)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.export_button.click()

    dialog = FakeMessageBox.instances[0]
    assert dialog.window_title == "Confirm Export Overwrite"
    assert str(tmp_path) in dialog.text
    assert "1 Result Image" in dialog.text
    assert "1 Debug Image" in dialog.text
    assert "measurements.xlsx" in dialog.text
    assert dialog.buttons == [
        ("Cancel", FakeMessageBox.ButtonRole.RejectRole),
        ("Overwrite", FakeMessageBox.ButtonRole.AcceptRole),
    ]
    assert dialog.default_button == "Cancel"
    assert window.status_label.text() == "Export canceled."
    assert window.file_table.item(0, 5).text() == "Not exported"
    assert existing_result.read_text() == "old result"
    assert existing_debug.read_text() == "old debug"
    assert existing_workbook.read_text() == "old workbook"


def test_app_overwrite_dialog_overwrite_replaces_existing_targets(
    qapp, tmp_path, monkeypatch
):
    image_path = tmp_path / "existing.tif"
    measured_folder = tmp_path / "measured_image"
    debug_folder = tmp_path / "debug_image"
    measured_folder.mkdir()
    debug_folder.mkdir()
    existing_result = measured_folder / "existing_result.png"
    existing_debug = debug_folder / "existing_debug.png"
    existing_workbook = measured_folder / "measurements.xlsx"
    existing_result.write_bytes(b"old result")
    existing_debug.write_bytes(b"old debug")
    existing_workbook.write_bytes(b"old workbook")
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

    class FakeMessageBox:
        class ButtonRole:
            RejectRole = "reject"
            AcceptRole = "accept"

        def __init__(self, parent=None):
            self._clicked_button = None

        def setWindowTitle(self, title):
            pass

        def setText(self, text):
            pass

        def addButton(self, text, role):
            return text

        def setDefaultButton(self, button):
            pass

        def exec(self):
            self._clicked_button = "Overwrite"
            return 0

        def clickedButton(self):
            return self._clicked_button

    monkeypatch.setattr(app_module, "QMessageBox", FakeMessageBox)
    window = create_window()

    window.add_image_paths([image_path])
    window.measure_current_button.click()
    window.export_button.click()

    assert window.status_label.text() == "Exported 1 measured image."
    assert window.file_table.item(0, 5).text() == "Exported"
    assert existing_result.read_bytes() != b"old result"
    assert existing_debug.read_bytes() != b"old debug"
    assert existing_workbook.read_bytes() != b"old workbook"


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


def _render_widget(widget) -> QImage:
    image = QImage(widget.size(), QImage.Format.Format_RGB32)
    widget.render(image)
    return image


def _queue_status_text(window, row_index: int) -> tuple[str, str]:
    image_widget = window.file_table.cellWidget(row_index, 1)
    primary = image_widget.findChild(QLabel, "QueueStatusPrimary")
    secondary = image_widget.findChild(QLabel, "QueueStatusSecondary")
    return primary.text(), secondary.text()


def _queue_file_text(window, row_index: int) -> tuple[str, str]:
    image_widget = window.file_table.cellWidget(row_index, 1)
    file_name = image_widget.findChild(QLabel, "QueueFileName")
    group = image_widget.findChild(QLabel, "QueueGroupBadge")
    return file_name.text(), group.text()


def _queue_group_badge_style(window, row_index: int) -> str:
    image_widget = window.file_table.cellWidget(row_index, 1)
    group = image_widget.findChild(QLabel, "QueueGroupBadge")
    return group.styleSheet()
