"""
Data loader module — uses ThaiAn merged CSV as primary source,
supplemented with a few individual CSVs for dashboard-specific columns.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent.parent / "data"

# Columns the dashboard expects that are NOT in the merged CSV
EXTRA_FILES = {
    "median_age":      ("median_age.csv",                       "Median age"),
    "old_dependency":  ("age-dependency-ratio-old.csv",         "Age dependency ratio, old (% of working-age population)"),
    "migrant_stock":   ("migrant-stock-total.csv",              "Total number of international immigrants"),
}

# Age-group columns from the merged CSV (different names from before)
AGE_COLS_MERGED = ['0-4 years', '5-14 years', '15-24 years', '25-64 years', '65+ years']


@lru_cache(maxsize=1)
def load_master_dataset(min_year: int = 1950, max_year: int = 2023) -> pd.DataFrame:
    """
    Load merged demographics CSV + extra columns into one DataFrame.
    Cached with @lru_cache — computed once per session.
    """
    merged_path = DATA_DIR / "merged_demographics.csv"
    if not merged_path.exists():
        raise FileNotFoundError(
            f"merged_demographics.csv not found at {merged_path}. "
            "Run: python scripts/merge_datasets.py"
        )

    df = pd.read_csv(merged_path)

    # ── Rename columns to match dashboard expectations ──────────────
    renames = {
        "Life expectancy at birth": "Life expectancy",
        "Annual net migration rate": "Net migration rate",
    }
    df.rename(columns={k: v for k, v in renames.items() if k in df.columns}, inplace=True)

    # ── Merge extra columns from individual CSVs ────────────────────
    for key, (filename, col_name) in EXTRA_FILES.items():
        fpath = DATA_DIR / filename
        if not fpath.exists():
            continue
        extra = pd.read_csv(fpath)
        val_cols = [c for c in extra.columns if c not in ('Entity', 'Code', 'Year')]
        keep = col_name if col_name in val_cols else val_cols[0]
        extra = extra[['Entity', 'Code', 'Year', keep]].copy()
        extra.rename(columns={keep: col_name}, inplace=True)
        df = df.merge(extra, on=['Entity', 'Code', 'Year'], how='left')

    # ── Filter year range ───────────────────────────────────────────
    df = df[(df['Year'] >= min_year) & (df['Year'] <= max_year)]

    # ── Derived columns ─────────────────────────────────────────────
    # Children = 0-4 + 5-14
    df['Children (0-14)'] = df['0-4 years'] + df['5-14 years']
    # Working age = 15-24 + 25-64
    df['Working age (15-64)'] = df['15-24 years'] + df['25-64 years']
    # Elderly = 65+
    df['Elderly (65+)'] = df['65+ years']

    total = df['Children (0-14)'] + df['Working age (15-64)'] + df['Elderly (65+)']

    df['Elderly share (%)'] = (df['Elderly (65+)'] / total) * 100
    df['Children share (%)'] = (df['Children (0-14)'] / total) * 100
    df['Young dependency ratio'] = (df['Children (0-14)'] / df['Working age (15-64)']) * 100

    # Alias for migrant stock
    if 'Total number of international immigrants' in df.columns:
        df['Migrant stock'] = df['Total number of international immigrants']

    return df


@lru_cache(maxsize=1)
def get_country_list() -> list[str]:
    """Return sorted list of country entities (no regions/aggregates)."""
    merged_path = DATA_DIR / "merged_demographics.csv"
    df = pd.read_csv(merged_path) if merged_path.exists() else pd.read_csv(DATA_DIR / "population.csv")
    has_code = df['Code'].notna()
    countries = df[has_code].copy()
    countries = countries[
        ~countries['Code'].str.startswith('OWID')
        & (countries['Code'].str.len() == 3)
    ]['Entity'].unique().tolist()
    return sorted(countries)


@lru_cache(maxsize=1)
def get_region_mapping() -> dict[str, str]:
    """Map country → continent."""
    region_map = {
        'China': 'Asia', 'India': 'Asia', 'Indonesia': 'Asia', 'Pakistan': 'Asia',
        'Japan': 'Asia', 'South Korea': 'Asia', 'Vietnam': 'Asia', 'Thailand': 'Asia',
        'Nigeria': 'Africa', 'Ethiopia': 'Africa', 'Tanzania': 'Africa',
        'Democratic Republic of Congo': 'Africa', 'South Africa': 'Africa',
        'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
        'Brazil': 'South America', 'Argentina': 'South America',
        'Germany': 'Europe', 'Italy': 'Europe', 'France': 'Europe',
        'United Kingdom': 'Europe', 'Ukraine': 'Europe', 'Syria': 'Asia',
        'Venezuela': 'South America', 'Afghanistan': 'Asia',
        'Australia': 'Oceania', 'New Zealand': 'Oceania',
        'Taiwan': 'Asia', 'Hong Kong': 'Asia',
        'United Arab Emirates': 'Asia', 'Qatar': 'Asia', 'Kuwait': 'Asia', 'Oman': 'Asia',
    }
    return region_map


if __name__ == "__main__":
    df = load_master_dataset()
    print(f"Master dataset: {df.shape}")
    print(f"Columns ({len(df.columns)}): {sorted(df.columns)}")
    print(f"Years: {int(df['Year'].min())} – {int(df['Year'].max())}")
    print(f"Countries: {df['Entity'].nunique()}")
    print(f"Sample (KOR 2023):")
    row = df[(df['Code'] == 'KOR') & (df['Year'] == 2023)]
    if not row.empty:
        for c in ['Entity','Year','Fertility rate','Life expectancy','Median age','Net migration rate','Child mortality rate','Death rate']:
            print(f"  {c}: {row[c].values[0]}")
