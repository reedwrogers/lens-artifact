"""Focused tests for capture-date ordering and photo filters (app/photos.py)."""
import os

import piexif
import pytest
from PIL import Image

from app import photos


def make_jpg(path, taken=None):
    Image.new("RGB", (8, 8), (128, 128, 128)).save(path, "JPEG")
    if taken:
        exif = {"0th": {}, "Exif": {36867: taken}, "GPS": {},
                "Interoperability": {}, "1st": {}, "thumbnail": None}
        piexif.insert(piexif.dump(exif), str(path))


@pytest.fixture()
def lib(tmp_path):
    pics = tmp_path / "pics"
    pics.mkdir()
    make_jpg(pics / "OLD.JPG", "2020:05:01 10:00:00")
    make_jpg(pics / "NEW.JPG", "2024:08:15 18:30:00")
    make_jpg(pics / "MID.JPG", "2022:01:10 12:00:00")
    noexif = pics / "NOEXIF.JPG"
    make_jpg(noexif)
    os.utime(noexif, (1577836800, 1577836800))  # 2020-01-01, older than all
    make_jpg(pics / "NEW_fix.JPG", "2025:01:01 00:00:00")
    return pics, tmp_path / "data"


def test_newest_first_by_taken(lib):
    pics, data = lib
    names = [i["name"] for i in photos.list_photos(pics, data)["items"]]
    assert names == ["NEW.JPG", "MID.JPG", "OLD.JPG", "NOEXIF.JPG"]


def test_fix_copies_and_non_images_excluded(lib):
    pics, data = lib
    (pics / "notes.txt").write_text("hi")
    names = [i["name"] for i in photos.list_photos(pics, data)["items"]]
    assert "NEW_fix.JPG" not in names and "notes.txt" not in names


def test_mtime_fallback_orders_without_exif(tmp_path):
    pics = tmp_path / "p"
    pics.mkdir()
    a, b = pics / "a.JPG", pics / "b.JPG"
    make_jpg(a)
    make_jpg(b)
    os.utime(a, (1600000000, 1600000000))
    os.utime(b, (1700000000, 1700000000))
    names = [i["name"] for i in photos.list_photos(pics, None)["items"]]
    assert names == ["b.JPG", "a.JPG"]


def test_search_filter(lib):
    pics, data = lib
    out = photos.list_photos(pics, data, search="new")
    assert [i["name"] for i in out["items"]] == ["NEW.JPG"]
    assert out["total"] == 1


def test_date_range_filter(lib):
    pics, data = lib
    out = photos.list_photos(pics, data, date_from="2021-01-01",
                             date_to="2023-12-31")
    assert [i["name"] for i in out["items"]] == ["MID.JPG"]


def test_bad_date_rejected(lib):
    pics, data = lib
    with pytest.raises(ValueError):
        photos.list_photos(pics, data, date_from="15-08-2024")


def test_cache_survives_rescan(lib):
    pics, data = lib
    first = photos.list_photos(pics, data)
    assert (data / "photo_index.json").is_file()
    second = photos.list_photos(pics, data)
    assert [i["name"] for i in first["items"]] == \
        [i["name"] for i in second["items"]]


def test_fixed_flag_marks_edited_photos(lib):
    pics, data = lib
    flags = {i["name"]: i["fixed"] for i in photos.list_photos(pics, data)["items"]}
    assert flags["NEW.JPG"] is True
    assert flags["MID.JPG"] is False
    assert flags["OLD.JPG"] is False


def test_fixed_flag_appears_after_fix_created(lib):
    pics, data = lib
    before = {i["name"]: i["fixed"]
              for i in photos.list_photos(pics, data)["items"]}
    assert before["MID.JPG"] is False
    make_jpg(pics / "MID_fix.JPG", "2022:01:10 12:00:00")
    after = {i["name"]: i["fixed"]
             for i in photos.list_photos(pics, data)["items"]}
    assert after["MID.JPG"] is True
