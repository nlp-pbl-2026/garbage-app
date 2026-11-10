#!/usr/bin/env python3
"""Split 300-dpi Seiyo dictionary pages for the Windows OCR size limit."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "tmp/seiyo-source/render/dictionary-300")
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/seiyo-source/render/dictionary-300-halves")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for page in range(1, 27):
        path = args.input / f"dictionary-{page:02d}.png"
        with Image.open(path) as image:
            width, height = image.size
            split = height // 2
            overlap = 100
            image.crop((0, 0, width, split + overlap)).save(
                args.output / f"dictionary-{page:02d}-top.png"
            )
            image.crop((0, split - overlap, width, height)).save(
                args.output / f"dictionary-{page:02d}-bottom-y{split - overlap}.png"
            )
        print(path.name)


if __name__ == "__main__":
    main()
