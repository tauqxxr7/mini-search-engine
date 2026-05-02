"""Create a short demo GIF from captured screenshots."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
FRAMES = [
    ("1. Search homepage", ROOT / "docs" / "screenshots" / "search-ui.png"),
    ("2. Crawl page", ROOT / "docs" / "screenshots" / "crawl-page.png"),
    ("3. Ranked results", ROOT / "docs" / "screenshots" / "results-page.png"),
    ("4. Metrics API", ROOT / "docs" / "screenshots" / "metrics-api.png"),
]


def labeled_frame(label: str, path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB").resize((960, 633))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 960, 44), fill=(32, 33, 36))
    draw.text((18, 13), label, fill=(255, 255, 255))
    return image


def main() -> None:
    frames = [labeled_frame(label, path) for label, path in FRAMES]
    output = ROOT / "docs" / "demo.gif"
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=1200,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
