"""Generate locale JSON files from locales/fr.json using Google Translate."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Install: pip install deep-translator", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "locales"
SOURCE = LOCALES_DIR / "fr.json"

# At least 30 languages — code -> deep-translator target code
TARGET_LOCALES: dict[str, str] = {
    "en": "en",
    "es": "es",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "nl": "nl",
    "pl": "pl",
    "ro": "ro",
    "ar": "ar",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "tr": "tr",
    "sv": "sv",
    "da": "da",
    "no": "no",
    "fi": "fi",
    "cs": "cs",
    "hu": "hu",
    "el": "el",
    "he": "iw",
    "hi": "hi",
    "uk": "uk",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "ms": "ms",
    "ca": "ca",
    "bg": "bg",
    "hr": "hr",
    "sk": "sk",
    "sl": "sl",
    "lt": "lt",
    "lv": "lv",
    "et": "et",
    "fa": "fa",
    "bn": "bn",
    "ta": "ta",
    "ur": "ur",
}


def _protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    out = text
    for idx, token in enumerate(["{app_name}", "{name}", "{country}", "{zone}", "{sectors}", "{min}", "{date}", "{n}", "{query}", "{count}", "{id}"]):
        if token in out:
            key = f"__PH{idx}__"
            mapping[key] = token
            out = out.replace(token, key)
    return out, mapping


def _restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    out = text
    for key, token in mapping.items():
        out = out.replace(key, token)
    return out


def translate_text(text: str, target: str, *, retries: int = 3) -> str:
    if not text.strip():
        return text
    protected, mapping = _protect_placeholders(text)
    for attempt in range(retries):
        try:
            translated = GoogleTranslator(source="fr", target=target).translate(protected)
            return _restore_placeholders(translated, mapping)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                print(f"  WARN translate failed ({target}): {exc!s} -> keeping FR")
                return text
            time.sleep(1.5 * (attempt + 1))
    return text


def main() -> None:
    force = "--force" in sys.argv
    argv_locales = [arg for arg in sys.argv[1:] if arg != "--force"]
    workers = 6
    for arg in argv_locales:
        if arg.startswith("--workers="):
            workers = max(1, int(arg.split("=", 1)[1]))
    argv_locales = [arg for arg in argv_locales if not arg.startswith("--workers=")]
    if not SOURCE.is_file():
        print(f"Missing {SOURCE}", file=sys.stderr)
        sys.exit(1)
    with SOURCE.open(encoding="utf-8") as handle:
        source_data: dict[str, str] = json.load(handle)

    for locale, target in TARGET_LOCALES.items():
        dest = LOCALES_DIR / f"{locale}.json"
        if dest.is_file() and locale not in argv_locales and not force:
            print(f"Skip existing {locale}.json (pass locale code or --force to regenerate)")
            continue
        print(f"Generating {locale}.json ({len(source_data)} keys, {workers} workers)...")
        translated: dict[str, str] = {}

        def _translate_item(item: tuple[str, str]) -> tuple[str, str]:
            key, value = item
            return key, translate_text(value, target)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_translate_item, item): item[0]
                for item in source_data.items()
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                key, value = future.result()
                translated[key] = value
                if idx % 50 == 0:
                    print(f"  {locale}: {idx}/{len(source_data)}")
        with dest.open("w", encoding="utf-8") as handle:
            json.dump(translated, handle, ensure_ascii=False, indent=2)
        print(f"  -> {dest}")
        time.sleep(0.2)


if __name__ == "__main__":
    main()
