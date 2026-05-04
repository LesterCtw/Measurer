import numpy as np
import tifffile

from measurer.image_input import is_supported_2d_image, read_stem_zc_image


def test_read_stem_zc_image_reads_tiff_metadata_scale(tmp_path):
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

    loaded = read_stem_zc_image(image_path)

    assert np.array_equal(loaded.image, image)
    assert loaded.metadata_nm_per_px == 0.8
    assert is_supported_2d_image(loaded.image)


def test_read_stem_zc_image_reads_dm3_metadata_scale(monkeypatch, tmp_path):
    image_path = tmp_path / "metadata_scale.dm3"
    image_path.write_bytes(b"fake dm3")
    image = np.ones((4, 4), dtype=np.uint8)

    def fake_file_reader(filename):
        return [
            {
                "data": image,
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

    loaded = read_stem_zc_image(image_path)

    assert np.array_equal(loaded.image, image)
    assert loaded.metadata_nm_per_px == 0.8
