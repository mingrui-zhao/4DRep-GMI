#!/usr/bin/env python3
"""
Optimize teaser images for fast, lightweight web loading.

For every raster image in images/ (png/jpg/jpeg):
  * back up the original into the local (gitignored) archive/images-src/
  * downscale so the longest side is <= MAX_PX
  * re-encode as WebP (quality ~82), and remove the original png/jpg from
    the public images/ folder

WebP is ~60-75% smaller than PNG at equivalent quality and is supported by all
current browsers. After running this, run build_bundle.py so thumbnailUrl points
at the .webp files.

Requires Pillow (local dev only; NOT needed by the GitHub Actions build):
    python3 -m pip install Pillow

Usage:
    python scripts/optimize_images.py          # optimize all png/jpg in images/
    python scripts/optimize_images.py --check   # report what would change, no writes
"""

import os
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IMAGES = os.path.join(REPO, "images")
BACKUP = os.path.join(REPO, "archive", "images-src")

MAX_PX = 768
QUALITY = 82
SRC_EXTS = (".png", ".jpg", ".jpeg")


def optimize_one(path, check=False):
    stem, ext = os.path.splitext(os.path.basename(path))
    out = os.path.join(IMAGES, stem + ".webp")
    with Image.open(path) as im:
        w, h = im.size
        scale = min(1.0, MAX_PX / max(w, h))
        new = (max(1, round(w * scale)), max(1, round(h * scale)))
        before = os.path.getsize(path)
        if check:
            return (stem, before, None, (w, h), new)
        # backup original
        os.makedirs(BACKUP, exist_ok=True)
        shutil.copy2(path, os.path.join(BACKUP, os.path.basename(path)))
        im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
        if scale < 1.0:
            im = im.resize(new, Image.LANCZOS)
        im.save(out, "WEBP", quality=QUALITY, method=6)
    after = os.path.getsize(out)
    # remove the original raster from the public folder (kept in archive backup)
    if os.path.abspath(path) != os.path.abspath(out):
        os.remove(path)
    return (stem, before, after, (w, h), new)


def main():
    check = "--check" in sys.argv
    files = sorted(
        os.path.join(IMAGES, f) for f in os.listdir(IMAGES)
        if f.lower().endswith(SRC_EXTS)
    )
    if not files:
        print("No png/jpg images to optimize (already WebP?).")
        return
    tot_before = tot_after = 0
    for path in files:
        stem, before, after, old, new = optimize_one(path, check)
        tot_before += before
        if check:
            print(f"  {stem}: {before//1024}KB  {old} -> resize {new} + webp")
        else:
            tot_after += after
            print(f"  {stem}: {before//1024}KB png -> {after//1024}KB webp  "
                  f"({old[0]}x{old[1]} -> {new[0]}x{new[1]})")
    if check:
        print(f"[check] {len(files)} images, {tot_before//1024}KB current")
    else:
        saved = tot_before - tot_after
        print(f"\n{len(files)} images: {tot_before//1024}KB -> {tot_after//1024}KB "
              f"(saved {saved//1024}KB, {100*saved//max(1,tot_before)}%). "
              f"Originals backed up in archive/images-src/.")
        print("Next: python scripts/build_bundle.py  (re-points thumbnails to .webp)")


if __name__ == "__main__":
    main()
