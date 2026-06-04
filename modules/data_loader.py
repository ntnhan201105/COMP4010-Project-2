"""
Data loader module — loads, merges, and preprocesses OWID demographic data.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent.parent / "data"

# ── file → column mapping ──────────────────────────────────────────
INDICATOR_FILES = {
    "population":                 ("population.csv",                  "Population"),
    "fertility_rate":             ("fertility_rate.csv",              "Fertility rate"),
    "life_expectancy":            ("life_expectancy.csv",             "Life expectancy"),
    "median_age":                 ("median_age.csv",                  "Median age"),
    "median_age_proj":            ("median_age.csv",                  "Median age (Projected)"),
    "population_growth":          ("population_growth.csv",           "Population growth rate"),
    "crude_death_rate":           ("crude-death-rate.csv",            "Annual crude death rate"),
    "old_dependency":             ("age-dependency-ratio-old.csv",    "Age dependency ratio, old (% of working-age population)"),
    "migrant_stock":              ("migrant-stock-total.csv",         "Total number of international immigrants"),
}

# Age-group columns from population-by-broad-age-group.csv
AGE_GROUP_COLS = ['Ages 65+', 'Ages 25-64', 'Ages 15-24', 'Ages 5-14', 'Under-5s']

# ── helper: load a single indicator CSV ─────────────────────────────
def _load_csv(filename: str, col: str) -> pd.DataFrame:
    """Load one OWID CSV, rename value column, keep Entity/Code/Year."""
    df = pd.read_csv(DATA_DIR / filename)
    val_cols = [c for c in df.columns if c not in ('Entity', 'Code', 'Year')]
    # Keep the requested column (or first value column)
    keep = col if col in val_cols else val_cols[0]
    out = df[['Entity', 'Code', 'Year', keep]].copy()
    out.rename(columns={keep: col}, inplace=True)
    return out


# ── master dataset ──────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_master_dataset(min_year: int = 1950, max_year: int = 2023) -> pd.DataFrame:
    """
    Load and merge all demographic indicators into one master DataFrame.
    Returns a DataFrame with Entity, Code, Year, and all indicator columns.
    """
    dfs = {}

    # Load each indicator
    for key, (filename, col_name) in INDICATOR_FILES.items():
        try:
            df = _load_csv(filename, col_name)
            dfs[key] = df
        except FileNotFoundError:
            print(f"⚠  Missing file: {filename} — skipping {key}")
            continue

    # Start with population as the base (has the widest year range)
    base = dfs["population"][['Entity', 'Code', 'Year']].drop_duplicates()

    # Merge all indicators
    for key, df in dfs.items():
        base = base.merge(df, on=['Entity', 'Code', 'Year'], how='left')

    # Filter year range
    base = base[(base['Year'] >= min_year) & (base['Year'] <= max_year)]

    # ── add derived features ────────────────────────────────────────
    # Load age groups separately
    age_df = pd.read_csv(DATA_DIR / "population-by-broad-age-group.csv")
    base = base.merge(
        age_df[['Entity', 'Code', 'Year'] + AGE_GROUP_COLS],
        on=['Entity', 'Code', 'Year'], how='left'
    )

    # Children = Under-5s + Ages 5-14
    base['Children (0-14)'] = base['Under-5s'] + base['Ages 5-14']
    # Working age = 15-24 + 25-64
    base['Working age (15-64)'] = base['Ages 15-24'] + base['Ages 25-64']
    # Elderly = 65+
    base['Elderly (65+)'] = base['Ages 65+']

    # Young dependency ratio: (0-14) / (15-64) * 100
    base['Young dependency ratio'] = (
        base['Children (0-14)'] / base['Working age (15-64)'] * 100
    )

    # Elderly share
    base['Elderly share (%)'] = (
        base['Elderly (65+)']
        / (base['Children (0-14)'] + base['Working age (15-64)'] + base['Elderly (65+)'])
        * 100
    )

    # Children share
    base['Children share (%)'] = (
        base['Children (0-14)']
        / (base['Children (0-14)'] + base['Working age (15-64)'] + base['Elderly (65+)'])
        * 100
    )

    # Net migration rate (approximated — but we lack net migration... use migrant stock change)
    base['Migrant stock'] = base.get('Total number of international immigrants', np.nan)

    return base


@lru_cache(maxsize=1)
def get_country_list() -> list[str]:
    """Return list of actual country entities (no regions/aggregates)."""
    df = pd.read_csv(DATA_DIR / "population.csv")
    # Exclude regions and aggregates (they have no ISO code or code starts with OWID)
    has_code = df['Code'].notna()
    countries = df[has_code].copy()
    countries = countries[
        ~countries['Code'].str.startswith('OWID')
        & (countries['Code'].str.len() == 3)
    ]['Entity'].unique().tolist()
    return sorted(countries)


@lru_cache(maxsize=1)
def get_region_mapping() -> dict[str, str]:
    """Map country → continent using OWID continent data."""
    # Try to load from OWID continent data
    continent_path = DATA_DIR / ".." / ".." / "continents.csv"
    if continent_path.exists():
        cmap = pd.read_csv(continent_path)
        return dict(zip(cmap['Entity'], cmap['Continent']))

    # Fallback: hardcode major countries → region
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
    }
    return region_map


if __name__ == "__main__":
    # Quick test
    df = load_master_dataset()
    print(f"Master dataset: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Years: {df['Year'].min()} – {df['Year'].max()}")
    print(f"Countries: {df['Entity'].nunique()}")
    print(df.head())
