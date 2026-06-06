"""
predict_future.py — Simple linear regression per country × indicator
to extend demographics.parquet from 2023 → 2040.

Uses the last 15 years (2009–2023) to fit a trend line, then predicts
2024–2040 with reasonable constraints to prevent absurd values.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
INPUT = DATA_DIR / "demographics.parquet"
OUTPUT = DATA_DIR / "demographics.parquet"  # overwrite (adds is_predicted col)

# ── config ──────────────────────────────────────────────────────────
PREDICT_START = 2024
PREDICT_END = 2040
FIT_WINDOW = 15  # years of recent history to fit

# Indicators to predict: column → (floor, ceil)
INDICATORS: dict[str, tuple[float | None, float | None]] = {
    "fertility_rate":            (0.3, 10.0),
    "lifeExp":                   (None, 90.0),
    "net_migration_rate":         (None, None),
    "child_mortality":            (0.0, None),
    "death_rate":                 (2.0, 25.0),
    "birth_rate":                 (2.0, 60.0),
    "population_growth_rate":     (None, None),
    "natural_population_growth_rate": (None, None),
    "infant_mortality":           (0.0, None),
    "annual_population_change":   (None, None),
}


def fit_indicator(hist: pd.DataFrame, col: str) -> tuple[float, float]:
    """Return (slope, intercept) from linear regression on recent years."""
    sub = hist.dropna(subset=[col])
    if len(sub) < 5:
        # Flat projection: use last known value
        last_val = float(sub[col].iloc[-1]) if len(sub) > 0 else 0.0
        return 0.0, last_val
    X = sub[["year"]].values.astype(float)
    y = sub[col].values.astype(float)
    m = LinearRegression().fit(X, y)
    return float(m.coef_[0]), float(m.intercept_)


def main():
    print(f"Loading {INPUT} ...")
    df = pd.read_parquet(INPUT)

    # Remove any previous predictions
    if "is_predicted" in df.columns:
        df = df[df["is_predicted"] == False].drop(columns=["is_predicted"])
    df["is_predicted"] = False

    # Fit all models first: (iso, col) → (slope, intercept)
    print("  Fitting models per country × indicator ...")
    models: dict[str, dict[str, tuple[float, float]]] = {}
    countries = list(df.groupby("iso_alpha"))

    for idx, (iso, grp) in enumerate(countries):
        recent = grp[grp["year"].between(2024 - FIT_WINDOW, 2023)]
        models[iso] = {}
        for col in INDICATORS:
            if col in grp.columns:
                models[iso][col] = fit_indicator(recent, col)

        if (idx + 1) % 50 == 0:
            print(f"    ... {idx + 1}/{len(countries)} countries fitted")

    # Generate predictions — ONE row per country per year
    print("  Generating predicted rows ...")
    all_predictions = []

    for iso, grp in countries:
        template = grp.iloc[-1].to_dict()
        for yr in range(PREDICT_START, PREDICT_END + 1):
            row = template.copy()
            row["year"] = yr
            row["is_predicted"] = True

            for col, (floor, ceil) in INDICATORS.items():
                if col not in models[iso]:
                    continue
                slope, intercept = models[iso][col]
                value = slope * yr + intercept
                if floor is not None:
                    value = max(value, floor)
                if ceil is not None:
                    value = min(value, ceil)
                row[col] = round(value, 6)

            all_predictions.append(row)

    print(f"  Generated {len(all_predictions)} predicted rows")

    # Build output DataFrame
    df_pred = pd.DataFrame(all_predictions)
    for c in df.columns:
        if c not in df_pred.columns:
            df_pred[c] = np.nan
    df_pred = df_pred[df.columns.tolist()]

    # Preserve is_country flag
    iso_country_map = df.groupby("iso_alpha")["is_country"].first().to_dict()
    df_pred["is_country"] = df_pred["iso_alpha"].map(iso_country_map).fillna(True)

    df_out = pd.concat([df, df_pred], ignore_index=True)
    n_pred = len(df_out[df_out["is_predicted"]])

    print(f"  Output: {len(df_out)} rows ({n_pred} predicted)")
    print(f"  Years: {int(df_out['year'].min())} – {int(df_out['year'].max())}")

    # ── Verify ───────────────────────────────────────────────────────
    print("\n  KOR fertility (2020-2040):")
    kor = df_out[(df_out["iso_alpha"] == "KOR") & (df_out["year"] >= 2020)].sort_values("year")
    for _, r in kor.iterrows():
        tag = " [PRED]" if r["is_predicted"] else ""
        print(f"    {int(r['year'])}: {r['fertility_rate']:.4f}{tag}")

    print("\n  TWN fertility (2020-2040):")
    twn = df_out[(df_out["iso_alpha"] == "TWN") & (df_out["year"] >= 2020)].sort_values("year")
    for _, r in twn.iterrows():
        tag = " [PRED]" if r["is_predicted"] else ""
        print(f"    {int(r['year'])}: {r['fertility_rate']:.4f}{tag}")

    df_out.to_parquet(OUTPUT, index=False)
    print(f"\n  ✓ Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
