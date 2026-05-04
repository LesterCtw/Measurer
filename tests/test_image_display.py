import numpy as np

from measurer.image_display import normalize_to_uint8


def test_normalize_to_uint8_keeps_uint8_values_contiguous():
    image = np.arange(9, dtype=np.uint8).reshape(3, 3)[:, ::-1]

    display = normalize_to_uint8(image)

    assert display.dtype == np.uint8
    assert display.flags.c_contiguous
    np.testing.assert_array_equal(display, image)


def test_normalize_to_uint8_scales_positive_image_to_display_range():
    image = np.asarray([[0, 10], [20, 40]], dtype=np.uint16)

    display = normalize_to_uint8(image)

    np.testing.assert_array_equal(
        display,
        np.asarray([[0, 64], [128, 255]], dtype=np.uint8),
    )


def test_normalize_to_uint8_handles_all_dark_image():
    image = np.zeros((2, 3), dtype=np.uint16)

    display = normalize_to_uint8(image)

    np.testing.assert_array_equal(display, np.zeros((2, 3), dtype=np.uint8))
