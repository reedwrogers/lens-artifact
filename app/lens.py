"""Lens-artifact removal methods.

Ported from the original ``main.ipynb`` workflow: dirty-lens spots are only
visible in flat regions (sky, sea), so the main strategy is a strong median
filter applied per selected region, optionally gated on low variance. Extra
inpainting / smoothing methods are provided as alternatives.
"""

import cv2
import numpy as np

METHODS = {
    "adaptive_median": "Median, low-variance regions only (original notebook method)",
    "median": "Median on every selected region",
    "inpaint_telea": "Inpaint (Telea) on selected regions",
    "inpaint_ns": "Inpaint (Navier-Stokes) on selected regions",
    "bilateral": "Bilateral smooth on selected regions",
}

MAX_KERNEL = 199


def _odd_kernel(kernel_size):
    try:
        k = int(kernel_size)
    except (TypeError, ValueError):
        k = 31
    k = max(3, min(MAX_KERNEL, k))
    return k if k % 2 == 1 else k + 1 if k + 1 <= MAX_KERNEL else k - 1


def normalize_regions(regions, width, height, limit=200):
    """Validate/clip user-supplied region dicts to (x, y, w, h) int tuples."""
    clean = []
    for r in (regions or [])[:limit]:
        try:
            x, y, w, h = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        clean.append((x, y, w, h))
    return clean


def _median_region(region, kernel):
    out = np.zeros_like(region)
    for c in range(region.shape[2]):
        out[..., c] = cv2.medianBlur(region[..., c], kernel)
    return out


def apply_fix(image_rgb, regions, method="adaptive_median",
              kernel_size=31, variance_threshold=50.0, inpaint_radius=3):
    """Apply a fix method to RGB image regions. Returns a new array."""
    if method not in METHODS:
        raise ValueError(f"Unknown method: {method}")
    height, width = image_rgb.shape[:2]
    boxes = normalize_regions(regions, width, height)
    out = image_rgb.copy()
    if not boxes:
        return out

    kernel = _odd_kernel(kernel_size)

    if method in ("median", "adaptive_median"):
        for x, y, w, h in boxes:
            region = out[y:y + h, x:x + w]
            if method == "median":
                out[y:y + h, x:x + w] = _median_region(region, kernel)
            else:
                variance = float(np.var(region.astype(np.float32), axis=(0, 1)).mean())
                if variance < float(variance_threshold):
                    out[y:y + h, x:x + w] = _median_region(region, kernel)
    elif method in ("inpaint_telea", "inpaint_ns"):
        mask = np.zeros((height, width), dtype=np.uint8)
        for x, y, w, h in boxes:
            mask[y:y + h, x:x + w] = 255
        flag = cv2.INPAINT_TELEA if method == "inpaint_telea" else cv2.INPAINT_NS
        out = cv2.inpaint(out, mask, float(inpaint_radius), flag)
    elif method == "bilateral":
        for x, y, w, h in boxes:
            region = out[y:y + h, x:x + w]
            out[y:y + h, x:x + w] = cv2.bilateralFilter(region, kernel, 75, 75)
    return out
