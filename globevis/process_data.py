from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = PROJECT_ROOT / "data" / "merged_demographics.csv"
OUTPUT_PARQUET = Path(__file__).resolve().parent / "data" / "demographics.parquet"

SPOTLIGHT_ISOS = {"SYR", "YEM", "ARE", "QAT", "KWT", "OMN", "KOR", "TWN", "HKG", "JPN"}

# Choropleth matching uses Natural Earth iso_a3 values. These centroids are
# only needed for optional fly-to/story affordances; the globe polygons do not
# depend on them.
SPOTLIGHT_CENTROIDS = {
    "RWA": {"latitude": -1.9403, "longitude": 29.8739},
    "KHM": {"latitude": 12.5657, "longitude": 104.9910},
    "SYR": {"latitude": 34.8021, "longitude": 38.9968},
    "AFG": {"latitude": 33.9391, "longitude": 67.7100},
    "YEM": {"latitude": 15.5527, "longitude": 48.5164},
    "UKR": {"latitude": 48.3794, "longitude": 31.1656},
    "ARE": {"latitude": 23.4241, "longitude": 53.8478},
    "QAT": {"latitude": 25.3548, "longitude": 51.1839},
    "KWT": {"latitude": 29.3117, "longitude": 47.4818},
    "OMN": {"latitude": 21.4735, "longitude": 55.9754},
    "TUR": {"latitude": 38.9637, "longitude": 35.2433},
    "LBN": {"latitude": 33.8547, "longitude": 35.8623},
    "JOR": {"latitude": 30.5852, "longitude": 36.2384},
    "DEU": {"latitude": 51.1657, "longitude": 10.4515},
    "POL": {"latitude": 51.9194, "longitude": 19.1451},
    "PAK": {"latitude": 30.3753, "longitude": 69.3451},
    "IRN": {"latitude": 32.4279, "longitude": 53.6880},
    "KOR": {"latitude": 35.9078, "longitude": 127.7669},
    "TWN": {"latitude": 23.6978, "longitude": 120.9605},
    "HKG": {"latitude": 22.3193, "longitude": 114.1694},
    "JPN": {"latitude": 36.2048, "longitude": 138.2529},
}

COLUMN_MAP = {
    "Entity": "country",
    "Code": "iso_alpha",
    "Year": "year",
    "Population": "pop",
    "Annual population change": "annual_population_change",
    "Annual net migration rate": "net_migration_rate",
    "Birth rate": "birth_rate",
    "Child mortality rate": "child_mortality",
    "Death rate": "death_rate",
    "Fertility rate": "fertility_rate",
    "Infant mortality rate": "infant_mortality",
    "Life expectancy at birth": "lifeExp",
    "Natural population growth rate": "natural_population_growth_rate",
    "0-4 years": "age_0_4",
    "5-14 years": "age_5_14",
    "15-24 years": "age_15_24",
    "25-64 years": "age_25_64",
    "65+ years": "age_65_plus",
    "Population density": "population_density",
    "Population growth rate": "population_growth_rate",
}

NUMERIC_COLUMNS = [
    "year",
    "pop",
    "annual_population_change",
    "net_migration_rate",
    "birth_rate",
    "child_mortality",
    "death_rate",
    "fertility_rate",
    "infant_mortality",
    "lifeExp",
    "natural_population_growth_rate",
    "age_0_4",
    "age_5_14",
    "age_15_24",
    "age_25_64",
    "age_65_plus",
    "population_density",
    "population_growth_rate",
]


def _is_iso3(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return len(value) == 3 and value.isalpha() and value.isupper()


def add_centroids(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["latitude"] = df["iso_alpha"].map(
        lambda iso: SPOTLIGHT_CENTROIDS.get(iso, {}).get("latitude", 0.0)
    )
    df["longitude"] = df["iso_alpha"].map(
        lambda iso: SPOTLIGHT_CENTROIDS.get(iso, {}).get("longitude", 0.0)
    )
    return df


def main() -> None:
    print(f"Loading merged OWID demographics from {SOURCE_CSV}...")
    raw = pd.read_csv(SOURCE_CSV)
    df = raw.rename(columns=COLUMN_MAP)

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["year"] = df["year"].astype("Int64")
    df["iso_alpha"] = df["iso_alpha"].astype("string")

    countries = df[df["iso_alpha"].map(_is_iso3)].copy()
    countries["is_country"] = True

    world = df[df["country"].eq("World")].copy()
    if world.empty:
        print("No World entity found; computing an unweighted country mean baseline.")
        world = (
            countries.groupby("year", as_index=False)
            .agg(
                {
                    "pop": "sum",
                    "annual_population_change": "sum",
                    "net_migration_rate": "mean",
                    "birth_rate": "mean",
                    "child_mortality": "mean",
                    "death_rate": "mean",
                    "fertility_rate": "mean",
                    "infant_mortality": "mean",
                    "lifeExp": "mean",
                    "natural_population_growth_rate": "mean",
                    "age_0_4": "sum",
                    "age_5_14": "sum",
                    "age_15_24": "sum",
                    "age_25_64": "sum",
                    "age_65_plus": "sum",
                    "population_density": "mean",
                    "population_growth_rate": "mean",
                }
            )
        )
        world["country"] = "World"

    world["iso_alpha"] = "WORLD"
    world["is_country"] = False

    processed = pd.concat([countries, world], ignore_index=True)
    processed["is_spotlight"] = processed["iso_alpha"].isin(SPOTLIGHT_ISOS)
    processed = add_centroids(processed)

    processed = processed[
        [
            "country",
            "iso_alpha",
            "year",
            "is_country",
            "is_spotlight",
            "latitude",
            "longitude",
            "pop",
            "annual_population_change",
            "net_migration_rate",
            "birth_rate",
            "child_mortality",
            "death_rate",
            "fertility_rate",
            "infant_mortality",
            "lifeExp",
            "natural_population_growth_rate",
            "age_0_4",
            "age_5_14",
            "age_15_24",
            "age_25_64",
            "age_65_plus",
            "population_density",
            "population_growth_rate",
        ]
    ].sort_values(["is_country", "country", "year"], ascending=[False, True, True])

    duplicate_keys = processed.duplicated(["iso_alpha", "year"]).sum()
    if duplicate_keys:
        raise ValueError(f"Found {duplicate_keys} duplicate iso/year rows after processing.")

    OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    processed.to_parquet(OUTPUT_PARQUET, index=False)

    print(f"Saved real demographics parquet to {OUTPUT_PARQUET}")
    print(
        "Rows: "
        f"{len(processed):,}; countries: {countries['iso_alpha'].nunique():,}; "
        f"years: {int(processed['year'].min())}-{int(processed['year'].max())}"
    )
    print("Spotlight countries:", ", ".join(sorted(SPOTLIGHT_ISOS)))


if __name__ == "__main__":
    main()
