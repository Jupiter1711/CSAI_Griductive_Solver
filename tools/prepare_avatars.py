"""Crop character artwork into round-ready portraits at three @2x sizes.

Input:  assets/avatars/source/<slug>.(png|webp|jpg)  (raw artwork)
Output: assets/avatars/<size>/<slug>.png for size in 192, 128, 72
        (shown at 96, 64 and 36/28 px), plus crops.json with one entry per
        character that you can edit by hand and re-run.

Crop rule (from data/REDESIGN_BRIEF.md): square head-and-shoulders frame, eyes at about
40% of the height, head about 60% of the frame. Images are only ever scaled
DOWN with LANCZOS. If a crop is smaller than an output size, that size is
written at the crop's own resolution and a warning is printed; the artwork
needs a bigger source to be sharp at 2x zoom.

    python tools/prepare_avatars.py
    python tools/prepare_avatars.py --only goku vegeta --sheet sheet.png
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
AVATARS = ROOT / "assets" / "avatars"
SOURCE_DIR = AVATARS / "source"
CROPS_FILE = AVATARS / "crops.json"
SIZES = (192, 128, 72)
MIN_SOURCE_EDGE = 512
EYE_LINE = 0.40  # eyes at 40% of the frame height
HEAD_SHARE = 0.60  # head covers ~60% of the frame


def figure_box(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A").point(lambda a: 255 if a > 100 else 0)
    return alpha.getbbox() or (0, 0, image.width, image.height)


def auto_crop(image: Image.Image) -> dict[str, float]:
    """Guess the head from the opaque pixels near the top of the figure.

    Values are fractions of the figure box so they survive re-exports of the
    source at another resolution: cx (head centre x, of width), eye (eye
    line y, of height), head (head height, of height).
    """
    left, top, right, bottom = figure_box(image)
    width, height = right - left, bottom - top
    band = image.getchannel("A").crop((left, top, right, top + max(1, height // 7)))
    band = band.point(lambda a: 255 if a > 100 else 0)
    total = weighted = 0
    for x in range(band.width):
        column = band.crop((x, 0, x + 1, band.height)).histogram()[255]
        total += column
        weighted += column * x
    cx = (weighted / total) / width if total else 0.5
    head = 0.17  # anime figures are roughly six heads tall
    return {"cx": round(cx, 3), "eye": round(head * 0.62, 3), "head": head}


def crop_square(image: Image.Image, crop: dict[str, float]) -> Image.Image:
    left, top, right, bottom = figure_box(image)
    width, height = right - left, bottom - top
    side = max(8, int(crop["head"] * height / HEAD_SHARE))
    centre_x = left + crop["cx"] * width
    eye_y = top + crop["eye"] * height
    x0 = int(round(centre_x - side / 2))
    y0 = int(round(eye_y - EYE_LINE * side))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image.crop((x0, y0, x0 + side, y0 + side)), (0, 0))
    return canvas


def export(slug: str, square: Image.Image) -> list[str]:
    warnings = []
    for size in SIZES:
        folder = AVATARS / str(size)
        folder.mkdir(parents=True, exist_ok=True)
        if square.width >= size:
            out = square.resize((size, size), Image.LANCZOS)
        else:
            out = square  # never upscale
            warnings.append(f"{size}px wanted, crop is only {square.width}px")
        out.save(folder / f"{slug}.png")
    return warnings


def contact_sheet(slugs: list[str], path: Path) -> None:
    cols, cell = 8, 160
    rows = (len(slugs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 20)), (13, 14, 18))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(slugs):
        x, y = i % cols * cell, i // cols * (cell + 20)
        face = Image.open(AVATARS / "192" / f"{name}.png").convert("RGBA")
        face = face.resize((cell - 16, cell - 16), Image.LANCZOS)
        mask = Image.new("L", face.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, *face.size), fill=255)
        disc = Image.new("RGBA", face.size, (22, 24, 31, 255))
        disc.alpha_composite(face)
        sheet.paste(disc, (x + 8, y + 4), mask)
        draw.text((x + 8, y + cell - 8), name, fill=(154, 154, 163))
    sheet.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="slugs to process")
    parser.add_argument("--sheet", type=Path, help="save a contact sheet PNG")
    args = parser.parse_args()

    crops = json.loads(CROPS_FILE.read_text("utf-8")) if CROPS_FILE.exists() else {}
    sources = sorted(
        p for p in SOURCE_DIR.iterdir() if p.suffix.lower() in {".png", ".webp", ".jpg"}
    )
    done = []
    for path in sources:
        slug = path.stem
        if args.only and slug not in args.only:
            continue
        image = Image.open(path).convert("RGBA")
        notes = []
        if min(image.size) < MIN_SOURCE_EDGE:
            notes.append(f"source {image.width}x{image.height} < {MIN_SOURCE_EDGE}px")
        crop = crops.setdefault(slug, auto_crop(image))
        notes += export(slug, crop_square(image, crop))
        done.append(slug)
        print(f"{slug:22s} " + ("; ".join(notes) if notes else "ok"))

    CROPS_FILE.write_text(json.dumps(crops, indent=2, sort_keys=True) + "\n", "utf-8")
    if args.sheet and done:
        contact_sheet(done, args.sheet)


if __name__ == "__main__":
    main()
