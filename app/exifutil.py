"""Save ``*_fix`` copies next to originals, preserving metadata.

Mirrors the last cell of ``main.ipynb`` (EXIF transplant via piexif) and
additionally preserves filesystem dates (mtime/atime) so the fixed copy
carries the same date information as the original.
"""

import os
import shutil

from PIL import Image
import piexif

FIX_SUFFIX = "_fix"


def fix_path_for(original_path, suffix=FIX_SUFFIX):
    stem, ext = os.path.splitext(original_path)
    return f"{stem}{suffix}{ext}"


def save_fix_copy(original_path, fixed_rgb_array, suffix=FIX_SUFFIX, jpeg_quality=95):
    """Write the fixed image as ``<stem>_fix.<ext>`` beside the original.

    Returns ``(fix_path, exif_copied)``.
    """
    fix_path = fix_path_for(original_path, suffix)
    img = Image.fromarray(fixed_rgb_array)
    ext = os.path.splitext(original_path)[1].lower()

    exif_bytes = None
    try:
        with Image.open(original_path) as orig:
            raw = orig.info.get("exif")
            if raw:
                try:
                    exif_bytes = piexif.dump(piexif.load(raw))
                except Exception:
                    exif_bytes = bytes(raw)
    except Exception:
        exif_bytes = None

    save_kwargs = {"quality": jpeg_quality} if ext in (".jpg", ".jpeg") else {}
    if exif_bytes:
        try:
            img.save(fix_path, exif=exif_bytes, **save_kwargs)
        except Exception:
            img.save(fix_path, **save_kwargs)
            exif_bytes = None
    else:
        img.save(fix_path, **save_kwargs)

    # Keep the same date information (mtime/atime) and mode as the original.
    shutil.copystat(original_path, fix_path)
    return fix_path, exif_bytes is not None
