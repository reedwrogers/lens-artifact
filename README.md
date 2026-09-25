# Lens Artifact Studio

Self-hosted Docker app (runs on the home server) with two apps on the home page:

- **Lens Fixer** (`/lens`) — browse the photo library, draw boxes over lens
  artifacts, pick a fix method (median / adaptive median from the original
  notebook, inpainting, bilateral), preview, then save a `*_fix.JPG` copy
  **next to the original** with EXIF and file dates preserved. Originals are
  never overwritten. Edited photos show an `edited` badge; tick checkboxes
  to export a selection as a `.zip` (fixed copy included when it exists).
- **ASCII Studio** (`/ascii`) — upload an mp4, convert it to ASCII frames with
  the same method as the old `ascii_video.ipynb`, play it back in the browser,
  or download the frames JSON.

Everything from the old repo (notebooks, mp4s, extracted frames, labels,
`utils.py`, …) now lives under [`archive/`](archive/).

## Run it

```bash
cd /home/tars/Projects/lens-artifact
docker compose up -d --build
```

Then open `http://<server-ip>:8123` in a browser (two squares → pick an app).

The photo library is mounted from `/home/tars/Media/t9_mnt/Pictures/DCIM/100MSDCF`
(see `docker-compose.yml`); fixed copies land beside the originals as
`DSC0xxxx_fix.JPG`. ASCII uploads/frames persist in `./data` (git-ignored).

## Local dev (no Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PHOTOS_DIR=/home/tars/Media/t9_mnt/Pictures/DCIM/100MSDCF DATA_DIR=./data \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/ -q
```

## Layout

```text
app/
  main.py            FastAPI app + API
  lens.py            fix methods (median, adaptive median, inpaint, bilateral)
  exifutil.py        _fix saving with EXIF + date preservation
  ascii_art.py       mp4 → ASCII frames (ported from ascii_video.ipynb)
  default_labels.csv archived labels.csv, used to seed suggested regions
  static/            index.html (app squares), lens.html/js, ascii.html/js
archive/             all legacy notebooks, media, frames, scripts
data/                runtime ASCII uploads/jobs (created at runtime, ignored)
```
