"""Build a static data snapshot for the website.

Runs the same code as the FastAPI backend (app.py) and writes the results of
every endpoint that does NOT need an Anthropic API key into frontend/data/.
The dashboards load these files whenever the live API can't be reached, so
the stats pages always show information.

Usage (from the repo root, with requirements.txt installed):
    python scripts/build_snapshot.py

Re-run it whenever data/*.csv or data/*.json change, then commit frontend/data/.
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "data"

# app.py loads its data with relative paths and only calls Claude when a key is set.
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.pop("ANTHROPIC_API_KEY", None)
import app  # noqa: E402


def write(name, payload):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main():
    predictions = app.predictions()
    talent = app.talent_predictions()
    areas = sorted({r["area"] for r in predictions})
    sectors = sorted({r["sector"] for r in talent})

    write("predictions.json", predictions)
    write("area-codes.json", {k: int(v) for k, v in app.area_codes().items()})
    write("deals.json", {a: asyncio.run(app.deals(a)) for a in areas})
    write("talent-predictions.json", talent)
    write("talent-sector-codes.json", {k: int(v) for k, v in app.talent_sector_codes().items()})
    write("talent-moves.json", {s: app.talent_moves(s) for s in sectors})

    latest_office = max((r["year"], r["quarter"]) for r in predictions)
    latest_talent = max((r["year"], r["quarter"]) for r in talent)
    write("meta.json", {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_date": date.today().isoformat(),
        "office_latest_period": f"{latest_office[0]} {latest_office[1]}",
        "talent_latest_period": f"{latest_talent[0]} {latest_talent[1]}",
        "note": "Built by scripts/build_snapshot.py from the data/ folder using the same model as the API.",
    })


if __name__ == "__main__":
    main()
