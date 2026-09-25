"""Export endpoint helpers: fixed-preferred zip of selected photos (app/main.py)."""
import io
import zipfile

import pytest
from fastapi import HTTPException
from PIL import Image

from app import main


def make_jpg(path, color=(10, 20, 30)):
    Image.new("RGB", (8, 8), color).save(path, "JPEG")


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    pics = tmp_path / "pics"
    pics.mkdir()
    make_jpg(pics / "A.JPG", (200, 0, 0))
    make_jpg(pics / "B.JPG", (0, 200, 0))
    make_jpg(pics / "A_fix.JPG", (0, 0, 200))
    monkeypatch.setattr(main, "PHOTOS_DIR", pics)
    return pics


def _names(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}


def test_export_prefers_fix_copy(lib):
    blob = main.build_export_zip(["A.JPG", "B.JPG"])
    got = _names(blob)
    assert set(got) == {"A_fix.JPG", "B.JPG"}
    assert got["A_fix.JPG"] == (lib / "A_fix.JPG").read_bytes()
    assert got["B.JPG"] == (lib / "B.JPG").read_bytes()


def test_export_single_unedited(lib):
    got = _names(main.build_export_zip(["B.JPG"]))
    assert set(got) == {"B.JPG"}


def test_export_empty_rejected(lib):
    with pytest.raises(HTTPException):
        main.build_export_zip([])


def test_export_unknown_name_rejected(lib):
    with pytest.raises(HTTPException):
        main.build_export_zip(["NOPE.JPG"])


def test_export_traversal_rejected(lib):
    with pytest.raises(HTTPException):
        main.build_export_zip(["../secret.JPG"])


def test_export_too_many_rejected(lib, monkeypatch):
    monkeypatch.setattr(main, "MAX_EXPORT_FILES", 2)
    with pytest.raises(HTTPException):
        main.build_export_zip(["A.JPG", "B.JPG", "A.JPG"])
