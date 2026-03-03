#!/usr/bin/env python3
"""Calibrate impact multipliers from historical events.

Usage:
  ALPHA_VANTAGE_KEY=... python3 tools/impact-model/calibrate.py

Outputs:
  data/impact-model/coefficients.json
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "impact-model"
CACHE_DIR = DATA_DIR / "cache"
EVENTS_FILE = DATA_DIR / "events.json"
ASSETS_FILE = DATA_DIR / "assets.json"
OUTPUT_FILE = DATA_DIR / "coefficients.json"

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "").strip()
if not ALPHA_VANTAGE_KEY:
    raise SystemExit("Missing ALPHA_VANTAGE_KEY env var")

CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_series(symbol: str) -> dict:
    cache_file = CACHE_DIR / f"{symbol}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    params = urlencode(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_KEY,
        }
    )
    url = f"https://www.alphavantage.co/query?{params}"
    with urlopen(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    cache_file.write_text(json.dumps(data))
    time.sleep(12)  # Alpha Vantage free tier throttle
    return data


def date_shift(date_str: str, days: int) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


def find_trading_date(series: dict, target: str, direction: int) -> str | None:
    dates = sorted(series.keys())
    if not dates:
        return None
    if direction >= 0:
        for d in dates:
            if d >= target:
                return d
    else:
        for d in reversed(dates):
            if d <= target:
                return d
    return None


def pct_change(series: dict, start_date: str, end_date: str) -> float | None:
    start = find_trading_date(series, start_date, -1)
    end = find_trading_date(series, end_date, 1)
    if not start or not end:
        return None
    try:
        start_close = float(series[start]["4. close"])
        end_close = float(series[end]["4. close"])
    except (KeyError, ValueError):
        return None
    if start_close == 0:
        return None
    return (end_close - start_close) / start_close * 100


def main() -> None:
    events = json.loads(EVENTS_FILE.read_text())
    assets = json.loads(ASSETS_FILE.read_text())

    sector_returns: dict[str, list[float]] = {}
    asset_returns: dict[str, list[float]] = {}
    category_returns: dict[str, list[float]] = {}

    for event in events:
        window = event.get("window", {"pre_days": 1, "post_days": 3})
        start = date_shift(event["date"], -window.get("pre_days", 1))
        end = date_shift(event["date"], window.get("post_days", 3))
        category = event.get("category", "unknown")

        for symbol in event.get("tickers", []):
            data = fetch_series(symbol)
            series = data.get("Time Series (Daily)", {})
            if not series:
                continue
            change = pct_change(series, start, end)
            if change is None:
                continue

            category_returns.setdefault(category, []).append(abs(change))

            for asset_id, meta in assets.items():
                if meta.get("ticker") == symbol:
                    sector = meta.get("sector", "other")
                    sector_returns.setdefault(sector, []).append(abs(change))
                    asset_returns.setdefault(asset_id, []).append(abs(change))

    all_returns = [val for vals in sector_returns.values() for val in vals]
    baseline = median(all_returns) if all_returns else 1.0

    def normalize(values: list[float]) -> float:
        if not values:
            return 1.0
        avg = sum(values) / len(values)
        ratio = avg / baseline if baseline else 1.0
        return max(0.6, min(1.6, ratio))

    sector_multipliers = {sector: normalize(vals) for sector, vals in sector_returns.items()}
    asset_multipliers = {asset: normalize(vals) for asset, vals in asset_returns.items()}
    category_multipliers = {cat: normalize(vals) for cat, vals in category_returns.items()}

    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "baseline_median_abs_move": baseline,
        "sector_multipliers": sector_multipliers,
        "asset_multipliers": asset_multipliers,
        "category_multipliers": category_multipliers,
        "notes": "Multipliers are based on median-anchored absolute event returns. Clamp range 0.6–1.6.",
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
