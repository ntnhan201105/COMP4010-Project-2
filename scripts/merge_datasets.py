"""Merge Our World in Data demographic datasets into one analysis-ready CSV.

The input files share the natural key (Entity, Code, Year). This script keeps
that grain intact, validates one-row-per-key in every source, avoids duplicate
semantic datasets, and writes a compact quality report next to the output CSV.
"""

from __future__ import annotations

import argparse
from functools import reduce
from pathlib import Path
from typing import Iterable

import pandas as pd


KEY_COLUMNS = ["Entity", "Code", "Year"]
AGE_COLUMNS = ["0-4 years", "5-14 years", "15-24 years", "25-64 years", "65+ years"]

# `age-structure` and `population-by-age-group` contain the same measures.
# Keep one canonical copy to avoid duplicated columns with identical meaning.
DATASETS = {
    "population": {
        "file": "population/population.csv",
        "rename": {"all years": "Population"},
    },
    "annual-change-in-population": {
        "file": "annual-change-in-population/annual-change-in-population.csv",
        "rename": {"all years": "Annual population change"},
    },
    "annual-net-migration-rate": {
        "file": "annual-net-migration-rate/annual-net-migration-rate.csv",
    },
    "birth-rate": {
        "file": "birth-rate/birth-rate.csv",
    },
    "child-mortality-rate": {
        "file": "child-mortality-rate/child-mortality-rate.csv",
    },
    "death-rate": {
        "file": "death-rate/death-rate.csv",
    },
    "infant-mortality-rate": {
        "file": "infant-mortality-rate/infant-mortality-rate.csv",
    },
    "life-expectancy-at-birth": {
        "file": "life-expectancy-at-birth/life-expectancy-at-birth.csv",
    },
    "natural-population-growth-rate": {
        "file": "natural-population-growth-rate/natural-population-growth-rate.csv",
    },
    "population-by-age-group": {
        "file": "population-by-age-group/population-by-age-group.csv",
    },
    "population-density": {
        "file": "population-density/population-density.csv",
    },
    "population-growth-rate": {
        "file": "population-growth-rate/population-growth-rate.csv",
    },
}

SKIPPED_DUPLICATE_DATASETS = [
    {
        "skipped": "age-structure",
        "skipped_file": "age-structure/age-structure.csv",
        "canonical": "population-by-age-group",
        "canonical_file": "population-by-age-group/population-by-age-group.csv",
        "columns": KEY_COLUMNS + AGE_COLUMNS,
        "reason": (
            "same values as population-by-age-group; skipped to avoid duplicate "
            "semantic columns"
        ),
    }
]

NON_NEGATIVE_COLUMNS = [
    "Population",
    "Birth rate",
    "Child mortality rate",
    "Death rate",
    "Infant mortality rate",
    "Life expectancy at birth",
    "Population density",
    "0-4 years",
    "5-14 years",
    "15-24 years",
    "25-64 years",
    "65+ years",
]

def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Merge demographic CSV files into one validated dataset."
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=project_root / "datasets",
        help="Directory containing the source dataset folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "data" / "merged_demographics.csv",
        help="Destination path for the merged CSV.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=project_root / "data" / "merge_report.txt",
        help="Destination path for the merge quality report.",
    )
    return parser.parse_args()


def read_dataset(datasets_dir: Path, dataset_name: str, config: dict) -> pd.DataFrame:
    path = datasets_dir / config["file"]
    if not path.exists():
        raise FileNotFoundError(f"Missing source file for {dataset_name}: {path}")

    df = pd.read_csv(path)
    missing_key_columns = [column for column in KEY_COLUMNS if column not in df.columns]
    if missing_key_columns:
        raise ValueError(f"{dataset_name} is missing key columns: {missing_key_columns}")

    duplicate_count = int(df.duplicated(KEY_COLUMNS).sum())
    if duplicate_count:
        examples = df.loc[df.duplicated(KEY_COLUMNS, keep=False), KEY_COLUMNS].head(10)
        raise ValueError(
            f"{dataset_name} has {duplicate_count} duplicate key rows.\n{examples}"
        )

    df = df.rename(columns=config.get("rename", {}))
    non_key_columns = [column for column in df.columns if column not in KEY_COLUMNS]
    if not non_key_columns:
        raise ValueError(f"{dataset_name} has no measure columns to merge.")

    return df[KEY_COLUMNS + non_key_columns]


def assert_no_semantic_duplicate_columns(frames: dict[str, pd.DataFrame]) -> None:
    seen: dict[str, str] = {}
    duplicate_messages: list[str] = []

    for dataset_name, df in frames.items():
        for column in df.columns:
            if column in KEY_COLUMNS:
                continue
            if column in seen:
                duplicate_messages.append(f"{column}: {seen[column]} and {dataset_name}")
            else:
                seen[column] = dataset_name

    if duplicate_messages:
        details = "\n".join(duplicate_messages)
        raise ValueError(f"Duplicate semantic measure columns found:\n{details}")


def verify_skipped_duplicate_sources(datasets_dir: Path) -> None:
    for duplicate in SKIPPED_DUPLICATE_DATASETS:
        skipped_path = datasets_dir / duplicate["skipped_file"]
        canonical_path = datasets_dir / duplicate["canonical_file"]
        if not skipped_path.exists() or not canonical_path.exists():
            raise FileNotFoundError(
                "Cannot verify skipped duplicate dataset: "
                f"{skipped_path} or {canonical_path} is missing."
            )

        columns = duplicate["columns"]
        skipped_df = pd.read_csv(skipped_path)
        canonical_df = pd.read_csv(canonical_path)

        for label, df in [
            (duplicate["skipped"], skipped_df),
            (duplicate["canonical"], canonical_df),
        ]:
            missing_columns = [column for column in columns if column not in df.columns]
            if missing_columns:
                raise ValueError(
                    f"{label} is missing columns needed for duplicate verification: "
                    f"{missing_columns}"
                )

        sort_key = KEY_COLUMNS
        skipped_normalized = skipped_df[columns].sort_values(sort_key).reset_index(drop=True)
        canonical_normalized = (
            canonical_df[columns].sort_values(sort_key).reset_index(drop=True)
        )

        if not skipped_normalized.equals(canonical_normalized):
            raise ValueError(
                f"{duplicate['skipped']} is no longer identical to "
                f"{duplicate['canonical']}; review before skipping it."
            )


def merge_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    merged = reduce(
        lambda left, right: left.merge(right, on=KEY_COLUMNS, how="outer", validate="one_to_one"),
        frames,
    )
    merged = merged.sort_values(["Entity", "Year", "Code"], na_position="last").reset_index(
        drop=True
    )

    duplicate_count = int(merged.duplicated(KEY_COLUMNS).sum())
    if duplicate_count:
        raise ValueError(f"Merged dataset has {duplicate_count} duplicate key rows.")

    return merged


def validate_values(merged: pd.DataFrame) -> list[str]:
    warnings: list[str] = []

    if not pd.api.types.is_integer_dtype(merged["Year"]):
        warnings.append("Year is not stored as an integer dtype.")

    year_min = int(merged["Year"].min())
    year_max = int(merged["Year"].max())
    if year_min < 1950 or year_max > 2023:
        warnings.append(f"Unexpected year range: {year_min}-{year_max}.")

    for column in NON_NEGATIVE_COLUMNS:
        if column in merged.columns:
            invalid_count = int((merged[column].dropna() < 0).sum())
            if invalid_count:
                warnings.append(f"{column} has {invalid_count} negative values.")

    if {"Population", *AGE_COLUMNS}.issubset(merged.columns):
        age_sum = merged[AGE_COLUMNS].sum(axis=1, min_count=len(AGE_COLUMNS))
        comparable = merged["Population"].notna() & age_sum.notna()
        # Population and age-group values are whole-person estimates. Use a small
        # relative tolerance to allow source rounding without hiding real mismatch.
        relative_gap = ((age_sum - merged["Population"]).abs() / merged["Population"]).where(
            comparable
        )
        mismatch_count = int((relative_gap > 0.001).sum())
        if mismatch_count:
            max_gap = float(relative_gap.max(skipna=True))
            warnings.append(
                "Age-group population sum differs from total Population by more than "
                f"0.1% for {mismatch_count} rows; max relative gap={max_gap:.4%}."
            )

    return warnings


def build_report(
    merged: pd.DataFrame,
    source_frames: dict[str, pd.DataFrame],
    warnings: list[str],
) -> str:
    lines = [
        "Merge report",
        "============",
        "",
        f"Output rows: {len(merged):,}",
        f"Output columns: {len(merged.columns):,}",
        f"Grain: one row per Entity, Code, Year",
        f"Year range: {int(merged['Year'].min())}-{int(merged['Year'].max())}",
        f"Entities: {merged['Entity'].nunique():,}",
        f"Rows with missing Code: {int(merged['Code'].isna().sum()):,}",
        "",
        "Included sources:",
    ]

    for dataset_name, df in source_frames.items():
        measures = [column for column in df.columns if column not in KEY_COLUMNS]
        lines.append(
            f"- {dataset_name}: {len(df):,} rows; measures: {', '.join(measures)}"
        )

    lines.extend(
        [
            "",
            "Skipped sources:",
        ]
    )
    lines.extend(
        f"- {duplicate['skipped']}: {duplicate['reason']}."
        for duplicate in SKIPPED_DUPLICATE_DATASETS
    )

    lines.extend(
        [
            "",
            "Quality checks:",
            "- No duplicate keys in source files.",
            "- No duplicate keys after merge.",
            "- One-to-one merge validation enforced for every source.",
            "- Skipped duplicate datasets verified against their canonical source.",
        ]
    )

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- No semantic value warnings detected.")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    verify_skipped_duplicate_sources(args.datasets_dir)
    source_frames = {
        dataset_name: read_dataset(args.datasets_dir, dataset_name, config)
        for dataset_name, config in DATASETS.items()
    }

    assert_no_semantic_duplicate_columns(source_frames)
    merged = merge_frames(source_frames.values())
    warnings = validate_values(merged)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(merged, source_frames, warnings), encoding="utf-8")

    print(f"Merged CSV written to: {args.output}")
    print(f"Merge report written to: {args.report}")
    print(f"Rows: {len(merged):,}; Columns: {len(merged.columns):,}")
    if warnings:
        print(f"Completed with {len(warnings)} warning(s). See report for details.")
    else:
        print("Completed with no semantic value warnings.")


if __name__ == "__main__":
    main()
