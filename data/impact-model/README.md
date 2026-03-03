# Calibration Pipeline

This folder holds the data sources and calibration outputs used by the simulator.

## Files
- `events.json` — historical event list (date, category, tickers)
- `assets.json` — asset registry and sector mapping
- `coefficients.json` — generated calibration multipliers (optional)

## Generate coefficients
From repo root:

```bash
ALPHA_VANTAGE_KEY=YOUR_KEY python3 tools/impact-model/calibrate.py
```

This writes `data/impact-model/coefficients.json`.

## Notes
- If `coefficients.json` exists, the frontend will automatically load it.
- If it doesn't exist, the simulator falls back to heuristic weights.
