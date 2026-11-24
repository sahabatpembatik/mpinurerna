#!/usr/bin/env python3
"""Compress images in ecoquest/mobile, or in a directory passed with --directory."""

import argparse
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError as error:
    raise SystemExit("Pillow is required. Install it with: python -m pip install Pillow") from error


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif"}
METADATA_KEYS = ("icc_profile", "exif", "dpi")


def compress_image(path, quality):
    with Image.open(path) as image:
        image.load()
        image_format = image.format
        if image_format not in {"PNG", "JPEG"}:
            return None

        original_size = path.stat().st_size
        original_pixels = image.convert("RGBA").tobytes() if image_format == "PNG" else None
        options = {key: image.info[key] for key in METADATA_KEYS if key in image.info}

        if image_format == "PNG" and "transparency" in image.info:
            options["transparency"] = image.info["transparency"]

        output = BytesIO()
        if image_format == "PNG":
            image.save(output, format="PNG", optimize=True, compress_level=9, **options)
        else:
            image.save(
                output,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
                **options,
            )

        compressed = output.getvalue()
        if len(compressed) >= original_size:
            return 0

        with Image.open(BytesIO(compressed)) as check:
            if check.format != image_format or check.size != image.size:
                raise ValueError("compressed image format or dimensions changed")
            if original_pixels is not None and check.convert("RGBA").tobytes() != original_pixels:
                raise ValueError("PNG pixel verification failed")

    fd, temporary_path = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as temporary_file:
            temporary_file.write(compressed)
        os.replace(temporary_path, path)
    except BaseException:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise

    return original_size - len(compressed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parent / "ecoquest" / "mobile",
        help="image directory (default: ecoquest/mobile)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=82,
        help="JPEG quality from 1 to 95 (default: 82)",
    )
    args = parser.parse_args()

    if not 1 <= args.quality <= 95:
        parser.error("--quality must be between 1 and 95")
    if not args.directory.is_dir():
        parser.error("directory does not exist: {}".format(args.directory))

    compressed_count = 0
    skipped_count = 0
    bytes_saved = 0
    failures = []

    for path in args.directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            saved = compress_image(path, args.quality)
            if saved is None:
                skipped_count += 1
            elif saved:
                compressed_count += 1
                bytes_saved += saved
        except Exception as error:
            failures.append((path, error))
            print("Error: {}: {}".format(path, error), file=sys.stderr)

    print("Compressed: {} image(s)".format(compressed_count))
    print("Saved: {:.2f} MB".format(bytes_saved / (1024 * 1024)))
    print("Skipped or already optimized: {} image(s)".format(skipped_count))
    if failures:
        print("Failed: {} image(s)".format(len(failures)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
