"""Photo listing: newest-first by capture date, with search + date filters.

Capture date comes from EXIF DateTimeOriginal (falling back to the 0th-IFD
DateTime tag, then to file mtime). Results are cached in DATA_DIR so a
multi-thousand-photo library doesn't pay for EXIF parsing on every request;
cache entries are keyed on file size + mtime and re-read when those change.
"""

import json
from datetime import datetime
from pathlib import Path

import piexif

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
FIX_SUFFIX = "_fix"
EXIF_FMT = "%Y:%m:%d %H:%M:%S"


def read_taken(path: Path):
    """EXIF capture time, or None when missing/unparseable."""
    try:
        exif = piexif.load(str(path))
    except Exception:
        return None
    candidates = [
        exif.get("Exif", {}).get(36867),   # DateTimeOriginal
        exif.get("0th", {}).get(306),      # DateTime fallback
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            return datetime.strptime(
                raw.decode("utf-8", "ignore").strip(), EXIF_FMT)
        except (ValueError, TypeError):
            continue
    return None


def _cache_file(data_dir):
    return Path(data_dir) / "photo_index.json" if data_dir else None


def _load_cache(data_dir):
    cache = _cache_file(data_dir)
    if cache and cache.is_file():
        try:
            data = json.loads(cache.read_text())
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}


def scan(photos_dir, data_dir=None):
    """Return [{name, size, mtime, taken}] for all library images."""
    photos_dir = Path(photos_dir)
    cache = _load_cache(data_dir)
    entries = {}
    for p in photos_dir.iterdir():
        if not p.is_file() or p.suffix not in IMAGE_EXTS:
            continue
        if FIX_SUFFIX in p.stem:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        hit = cache.get(p.name)
        if hit and hit.get("size") == st.st_size and hit.get("mtime") == st.st_mtime:
            taken = hit.get("taken")
        else:
            dt = read_taken(p)
            taken = dt.isoformat() if dt else None
            entries[p.name] = {"size": st.st_size, "mtime": st.st_mtime,
                               "taken": taken}
        entries.setdefault(p.name, {"size": st.st_size, "mtime": st.st_mtime,
                                    "taken": hit.get("taken") if hit else None})
    cache_path = _cache_file(data_dir)
    if cache_path:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(entries))
        except OSError:
            pass
    return [{"name": n, **v} for n, v in entries.items()]


def _parse_day(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {label}, expected YYYY-MM-DD: {value!r}")


def _effective_ts(entry):
    if entry.get("taken"):
        try:
            return datetime.fromisoformat(entry["taken"]).timestamp()
        except ValueError:
            pass
    return entry["mtime"]


def list_photos(photos_dir, data_dir=None, search="", date_from=None,
                date_to=None, limit=200, offset=0):
    entries = scan(photos_dir, data_dir)
    if search:
        q = search.lower()
        entries = [e for e in entries if q in e["name"].lower()]
    day_from = _parse_day(date_from, "date_from") if date_from else None
    day_to = _parse_day(date_to, "date_to") if date_to else None
    if day_from or day_to:
        kept = []
        for e in entries:
            day = datetime.fromtimestamp(_effective_ts(e)).date()
            if day_from and day < day_from:
                continue
            if day_to and day > day_to:
                continue
            kept.append(e)
        entries = kept
    entries.sort(key=lambda e: (_effective_ts(e), e["name"]), reverse=True)
    total = len(entries)
    return {"total": total, "items": entries[offset:offset + limit]}
