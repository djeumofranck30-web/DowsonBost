"""Fill missing keys in locale JSON files (translate delta from fr.json only)."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "locales"
SOURCE_PATH = LOCALES_DIR / "fr.json"

sys.path.insert(0, str(ROOT / "scripts"))
from generate_locales import TARGET_LOCALES, translate_text  # noqa: E402


def main() -> None:
    with SOURCE_PATH.open(encoding="utf-8") as handle:
        source: dict[str, str] = json.load(handle)

    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    workers = 8
    for arg in sys.argv[1:]:
        if arg.startswith("--workers="):
            workers = max(1, int(arg.split("=", 1)[1]))

    targets = {k: v for k, v in TARGET_LOCALES.items() if not argv or k in argv}
    targets["fr"] = "fr"

    for locale, target in targets.items():
        dest = LOCALES_DIR / f"{locale}.json"
        existing: dict[str, str] = {}
        if dest.is_file():
            with dest.open(encoding="utf-8") as handle:
                existing = json.load(handle)

        missing = {k: v for k, v in source.items() if k not in existing}
        if not missing:
            print(f"{locale}: complete ({len(existing)} keys)")
            continue

        print(f"{locale}: translating {len(missing)} missing keys…")

        def _one(item: tuple[str, str]) -> tuple[str, str]:
            key, value = item
            if locale == "fr":
                return key, value
            return key, translate_text(value, target)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, item) for item in missing.items()]
            for future in as_completed(futures):
                key, value = future.result()
                existing[key] = value

        with dest.open("w", encoding="utf-8") as handle:
            json.dump(existing, handle, ensure_ascii=False, indent=2)
        print(f"  -> {dest} ({len(existing)} keys)")


if __name__ == "__main__":
    main()
