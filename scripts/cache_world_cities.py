"""Pre-fetch city lists from Overpass and save to data/world_cities/{CODE}.json."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "world_cities"

sys.path.insert(0, str(ROOT))

from world_cities import _fetch_cities_overpass_country, _city_cache  # noqa: E402
from world_geo import COUNTRY_NAME_TO_CODE, country_geo_schema, COUNTRY_OPTIONS  # noqa: E402


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    argv = set(sys.argv[1:])
    skip_existing = "--force" not in argv
    targets = [c for c in COUNTRY_OPTIONS if not country_geo_schema(c)]
    if argv - {"--force"}:
        wanted = {name.casefold() for name in argv - {"--force"}}
        targets = [c for c in targets if c.casefold() in wanted]

    for idx, country in enumerate(targets, start=1):
        code = COUNTRY_NAME_TO_CODE.get(country, "")
        if not code:
            continue
        dest = DEST / f"{code}.json"
        if skip_existing and dest.is_file():
            print(f"[{idx}/{len(targets)}] Skip {code} ({country})")
            continue
        print(f"[{idx}/{len(targets)}] Fetch {code} ({country})…")
        _city_cache.clear()
        names = _fetch_cities_overpass_country(code)
        if not names:
            print(f"  WARN: no cities for {code}")
            continue
        with dest.open("w", encoding="utf-8") as handle:
            json.dump({"country": country, "code": code, "cities": list(names)}, handle, ensure_ascii=False, indent=2)
        print(f"  -> {len(names)} cities")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
