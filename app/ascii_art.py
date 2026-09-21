"""MP4 -> ASCII-frames conversion, ported from ``ascii_video.ipynb``.

Same character ramp and aspect-ratio compensation as the notebook; the only
change is that frames are read straight from the video with OpenCV instead of
requiring a prior ``ffmpeg`` PNG-dump step.
"""

import cv2
from PIL import Image

# ASCII characters used to represent pixels (from ascii_video.ipynb)
ASCII_CHARS = "@$B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


def resize(image, new_width=80):
    width, height = image.size
    ratio = height / width / 1.65  # adjust aspect ratio
    new_height = max(1, int(new_width * ratio))
    return image.resize((new_width, new_height))


def grayify(image):
    return image.convert("L")


def pixels_to_ascii(image):
    pixels = image.getdata()
    return "".join([ASCII_CHARS[int(pixel / 256 * len(ASCII_CHARS))] for pixel in pixels])


def pil_to_ascii(pil_image, width=80):
    image = resize(pil_image, width)
    image = grayify(image)
    ascii_str = pixels_to_ascii(image)
    img_width = image.width
    return "\n".join(
        [ascii_str[i:i + img_width] for i in range(0, len(ascii_str), img_width)]
    )


def video_to_ascii_frames(video_path, width=80, max_frames=600):
    """Convert a video file to a list of ASCII-frame strings."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    frames = []
    try:
        while len(frames) < max_frames:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frames.append(pil_to_ascii(Image.fromarray(frame_rgb), width=width))
    finally:
        cap.release()
    if not frames:
        raise ValueError("No frames could be read from the video")
    return frames
