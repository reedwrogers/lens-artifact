"""Lens Artifact Studio: self-hosted fixer + ASCII video studio."""

import csv
import io
import json
import os
import uuid
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import ascii_art, exifutil, photos
from .lens import METHODS, apply_fix
from .photos import IMAGE_EXTS

PHOTOS_DIR = Path(os.environ.get("PHOTOS_DIR", "/photos"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
LABELS_CSV = Path(os.environ.get(
    "LABELS_CSV", Path(__file__).parent / "default_labels.csv"))

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Lens Artifact Studio")


# ---------- helpers ----------

def _photo_path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Invalid file name")
    path = PHOTOS_DIR / name
    if not path.is_file() or path.suffix not in IMAGE_EXTS:
        raise HTTPException(404, "Image not found")
    return path


def _read_rgb(path: Path):
    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        raise HTTPException(422, "Could not decode image")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def _encode_jpeg(image_rgb, quality=90) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise HTTPException(500, "Could not encode preview")
    return bytes(buf)


def _default_boxes(image_name: str, width: int, height: int):
    """Seed regions from the archived labels.csv when names match."""
    if not LABELS_CSV.is_file():
        return []
    boxes = []
    try:
        with open(LABELS_CSV, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("image_name") != image_name:
                    continue
                try:
                    ref_w = float(row.get("image_width") or width)
                    ref_h = float(row.get("image_height") or height)
                    x = float(row["bbox_x"]) * width / ref_w
                    y = float(row["bbox_y"]) * height / ref_h
                    w = float(row["bbox_width"]) * width / ref_w
                    h = float(row["bbox_height"]) * height / ref_h
                except (KeyError, TypeError, ValueError):
                    continue
                boxes.append({"x": int(x), "y": int(y),
                              "w": int(w), "h": int(h),
                              "label": str(row.get("label_name", ""))})
    except OSError:
        return []
    return boxes


# ---------- pages ----------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/lens", include_in_schema=False)
def lens_page():
    return FileResponse(STATIC / "lens.html")


@app.get("/ascii", include_in_schema=False)
def ascii_page():
    return FileResponse(STATIC / "ascii.html")


# ---------- lens fixer API ----------

@app.get("/api/methods")
def list_methods():
    return {"methods": [{"id": k, "label": v} for k, v in METHODS.items()]}


@app.get("/api/photos")
def list_photos(search: str = "", limit: int = 200, offset: int = 0,
                date_from: str = None, date_to: str = None):
    """Newest capture date first. Filters: filename search + date range."""
    if not PHOTOS_DIR.is_dir():
        raise HTTPException(500, f"Photos dir not found: {PHOTOS_DIR}")
    try:
        return photos.list_photos(
            PHOTOS_DIR, DATA_DIR, search=search,
            date_from=date_from, date_to=date_to,
            limit=max(1, min(1000, limit)), offset=max(0, offset))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/photo/{name}")
def get_photo(name: str):
    return FileResponse(_photo_path(name))


@app.get("/api/thumb/{name}")
def get_thumb(name: str, size: int = 512):
    size = max(64, min(1024, size))
    img = _read_rgb(_photo_path(name))
    h, w = img.shape[:2]
    scale = min(1.0, size / max(h, w))
    small = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
    return Response(_encode_jpeg(small, 82), media_type="image/jpeg")


@app.get("/api/regions/suggest")
def suggest_regions(name: str):
    path = _photo_path(name)
    img = _read_rgb(path)
    h, w = img.shape[:2]
    return {"name": name, "width": w, "height": h,
            "boxes": _default_boxes(name, w, h)}


@app.post("/api/preview")
def preview(payload: dict):
    path = _photo_path(payload.get("name", ""))
    img = _read_rgb(path)
    try:
        fixed = apply_fix(
            img,
            payload.get("regions", []),
            method=payload.get("method", "adaptive_median"),
            kernel_size=payload.get("kernel_size", 31),
            variance_threshold=payload.get("variance_threshold", 50.0),
            inpaint_radius=payload.get("inpaint_radius", 3),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(_encode_jpeg(fixed), media_type="image/jpeg")


@app.post("/api/save")
def save(payload: dict):
    path = _photo_path(payload.get("name", ""))
    img = _read_rgb(path)
    try:
        fixed = apply_fix(
            img,
            payload.get("regions", []),
            method=payload.get("method", "adaptive_median"),
            kernel_size=payload.get("kernel_size", 31),
            variance_threshold=payload.get("variance_threshold", 50.0),
            inpaint_radius=payload.get("inpaint_radius", 3),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    fix_path, exif_copied = exifutil.save_fix_copy(str(path), fixed)
    return {"saved": Path(fix_path).name, "exif_copied": exif_copied}


# ---------- ASCII studio API ----------

def _job_dir(job_id: str) -> Path:
    if not job_id or "/" in job_id or "\\" in job_id or job_id.startswith("."):
        raise HTTPException(400, "Invalid job id")
    return DATA_DIR / "ascii" / job_id


@app.post("/api/ascii/jobs")
async def ascii_create_job(file: UploadFile = File(...),
                           width: int = Form(100),
                           max_frames: int = Form(300)):
    width = max(20, min(240, width))
    max_frames = max(1, min(2000, max_frames))
    job_id = uuid.uuid4().hex[:12]
    job_dir = _job_dir(job_id)
    (job_dir / "src").mkdir(parents=True, exist_ok=True)
    src = job_dir / "src" / (file.filename or "upload.mp4")
    with open(src, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    try:
        frames = ascii_art.video_to_ascii_frames(src, width=width,
                                                 max_frames=max_frames)
    except ValueError as e:
        raise HTTPException(422, str(e))
    (job_dir / "frames.json").write_text(json.dumps(frames))
    meta = {"id": job_id, "source": file.filename or "upload.mp4",
            "width": width, "n_frames": len(frames),
            "rows": frames[0].count("\n") + 1, "cols": width}
    (job_dir / "meta.json").write_text(json.dumps(meta))
    return meta


@app.get("/api/ascii/jobs")
def ascii_list_jobs():
    base = DATA_DIR / "ascii"
    jobs = []
    if base.is_dir():
        for meta_file in sorted(base.glob("*/meta.json")):
            try:
                jobs.append(json.loads(meta_file.read_text()))
            except (OSError, ValueError):
                continue
    return {"jobs": jobs}


@app.get("/api/ascii/jobs/{job_id}")
def ascii_get_job(job_id: str, include_frames: bool = True):
    job_dir = _job_dir(job_id)
    try:
        meta = json.loads((job_dir / "meta.json").read_text())
    except (OSError, ValueError):
        raise HTTPException(404, "Job not found")
    if include_frames:
        try:
            meta["frames"] = json.loads((job_dir / "frames.json").read_text())
        except (OSError, ValueError):
            raise HTTPException(404, "Frames missing")
    return meta


@app.get("/api/ascii/jobs/{job_id}/download")
def ascii_download(job_id: str):
    path = _job_dir(job_id) / "frames.json"
    if not path.is_file():
        raise HTTPException(404, "Job not found")
    return FileResponse(path, filename=f"ascii_{job_id}.json")


@app.delete("/api/ascii/jobs/{job_id}")
def ascii_delete(job_id: str):
    import shutil
    job_dir = _job_dir(job_id)
    if not job_dir.is_dir():
        raise HTTPException(404, "Job not found")
    shutil.rmtree(job_dir)
    return {"deleted": job_id}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/health")
def health():
    return {"ok": True, "photos_dir": str(PHOTOS_DIR),
            "photos_found": PHOTOS_DIR.is_dir() and
            sum(1 for _ in PHOTOS_DIR.iterdir()) or 0}


@app.exception_handler(404)
async def not_found(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(STATIC / "index.html")
