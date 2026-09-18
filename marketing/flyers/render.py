#!/usr/bin/env python3
"""Render flyer HTML to PNG (A4 preview) and PDF."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
HTML_DIR = ROOT / "html"
PNG_DIR = ROOT / "png"
PDF_DIR = ROOT / "pdf"
CHROME = "/opt/google/chrome/chrome"
W, H = 1240, 1754


def chrome_screenshot(html: Path, png: Path, profile: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        CHROME,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=4000",
        "--force-device-scale-factor=2",
        f"--user-data-dir={profile}",
        f"--window-size={W},{H}",
        f"--screenshot={png}",
        html.resolve().as_uri(),
    ]
    subprocess.run(
        cmd,
        check=True,
        timeout=60,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def png_to_pdf(png: Path, pdf: Path) -> None:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(png).convert("RGB")
    im = im.crop((0, 0, min(im.width, W * 2), min(im.height, H * 2)))
    im.save(pdf, "PDF", resolution=300.0)


def main() -> int:
    files = sorted(HTML_DIR.glob("*.html"))
    if not files:
        print("No HTML flyers found", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="db-flyers-chrome-") as tmp:
        profile = Path(tmp) / "profile"
        profile.mkdir()
        for html in files:
            png = PNG_DIR / (html.stem + ".png")
            pdf = PDF_DIR / (html.stem + ".pdf")
            print(f"render {html.name}", flush=True)
            chrome_screenshot(html, png, profile)
            png_to_pdf(png, pdf)
            print(f"  -> {png.relative_to(ROOT)} ({png.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
