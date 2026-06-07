from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget

try:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
except ImportError:  # pragma: no cover - deployment fallback
    KMeans = None
    PCA = None
    StandardScaler = None

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError:  # pragma: no cover - deployment fallback
    ExponentialSmoothing = None


# --- Story Configuration ---
REFUGEE_ORIGINS = ["SYR", "VEN"]
REFUGEE_HOSTS = ["TUR", "LBN", "JOR", "COL", "PER"]
REFUGEE_ISOS = ["SYR", "TUR", "LBN", "JOR", "VEN", "COL", "PER"]
MIGRATION_OUTFLOW = REFUGEE_ORIGINS
MIGRATION_INFLOW = REFUGEE_HOSTS

FERTILITY_COLLAPSE = ["KOR", "TWN", "JPN"]
FERTILITY_SCALE_SHIFT = ["CHN"]
FERTILITY_HIGH_GROWTH = ["NER", "TCD", "MLI"]
FERTILITY_ISOS = FERTILITY_COLLAPSE + FERTILITY_SCALE_SHIFT + FERTILITY_HIGH_GROWTH

AGE_GROUPS = [
    ("age_0_4", "0-4"),
    ("age_5_14", "5-14"),
    ("age_15_24", "15-24"),
    ("age_25_64", "25-64"),
    ("age_65_plus", "65+"),
]

SOCIOECONOMIC_METRICS = {
    "population_density": "Population density",
    "lifeExp": "Life expectancy",
    "child_mortality": "Child mortality",
    "population_growth_rate": "Population growth",
}

COUNTRY_META = {
    "SYR": {"name": "Syria", "color": "#ef4444", "role": "Conflict origin"},
    "VEN": {"name": "Venezuela", "color": "#f97316", "role": "Conflict origin"},
    "TUR": {"name": "Turkey", "color": "#22d3ee", "role": "Regional host"},
    "LBN": {"name": "Lebanon", "color": "#67e8f9", "role": "Regional host"},
    "JOR": {"name": "Jordan", "color": "#38bdf8", "role": "Regional host"},
    "COL": {"name": "Colombia", "color": "#0ea5e9", "role": "Regional host"},
    "PER": {"name": "Peru", "color": "#06b6d4", "role": "Regional host"},
    "KOR": {"name": "South Korea", "color": "#ef4444", "role": "Ultra-low fertility"},
    "TWN": {"name": "Taiwan", "color": "#fb7185", "role": "Ultra-low fertility"},
    "JPN": {"name": "Japan", "color": "#f97316", "role": "Ultra-low fertility"},
    "CHN": {"name": "China", "color": "#a78bfa", "role": "Scale shift"},
    "NER": {"name": "Niger", "color": "#22c55e", "role": "High-fertility contrast"},
    "TCD": {"name": "Chad", "color": "#84cc16", "role": "High-fertility contrast"},
    "MLI": {"name": "Mali", "color": "#14b8a6", "role": "High-fertility contrast"},
}

REFUGEE_COUNTRY_CHOICES = {iso: COUNTRY_META[iso]["name"] for iso in REFUGEE_ISOS}
FERTILITY_COUNTRY_CHOICES = {iso: COUNTRY_META[iso]["name"] for iso in FERTILITY_ISOS}

STORY_CONFIGS = {
    "migration": {
        "label": "Refugee crisis",
        "indicator": "net_migration_rate",
        "eyebrow": "Refugee crisis",
        "title": "Refugee Shockwaves",
        "copy": (
            "Conflict and collapse push people out of Syria and Venezuela, while nearby "
            "host countries absorb the demographic pressure."
        ),
        "isos": REFUGEE_ISOS,
        "origins": MIGRATION_OUTFLOW,
        "hosts": MIGRATION_INFLOW,
        "target": {"longitude": -35, "latitude": 20, "zoom": 0.42},
    },
    "fertility": {
        "label": "Ultra-low fertility cliff",
        "indicator": "fertility_rate",
        "eyebrow": "Ultra-low fertility",
        "title": "The Fertility Cliff",
        "copy": (
            "East Asia is falling far below replacement fertility, while high-growth Sahel "
            "countries show the opposite end of the demographic spectrum."
        ),
        "isos": FERTILITY_ISOS,
        "origins": FERTILITY_COLLAPSE + FERTILITY_SCALE_SHIFT,
        "hosts": FERTILITY_HIGH_GROWTH,
        "target": {"longitude": 83, "latitude": 24, "zoom": 0.72},
    },
}

INDICATOR_CONFIG = {
    "net_migration_rate": {
        "label": "Migration Rate",
        "col": "net_migration_rate",
        "unit": "migrants per 1,000 people",
    },
    "fertility_rate": {
        "label": "Fertility Rate",
        "col": "fertility_rate",
        "unit": "children per woman",
    },
    "life_expectancy": {
        "label": "Life Expectancy",
        "col": "lifeExp",
        "unit": "years",
    },
    "child_mortality": {
        "label": "Child Mortality",
        "col": "child_mortality",
        "unit": "% of children",
    },
    "death_rate": {
        "label": "Death Rate",
        "col": "death_rate",
        "unit": "deaths per 1,000 people",
    },
}


# --- Load Data ---
df_full = pd.read_parquet("./data/demographics.parquet")
df_full["year"] = df_full["year"].astype(int)
ACTUAL_MAX_YEAR = int(df_full["year"].max())
PROJECTION_END_YEAR = 2030
PROJECTION_WINDOW = 20

PROJECTED_COLUMNS = [
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


def _clip_projection(column: str, value: float) -> float:
    if not np.isfinite(value):
        return np.nan
    bounds = {
        "fertility_rate": (0.7, 8.0),
        "lifeExp": (20.0, 95.0),
        "child_mortality": (0.0, 50.0),
        "death_rate": (0.0, 45.0),
        "infant_mortality": (0.0, 150.0),
        "birth_rate": (0.0, 70.0),
        "net_migration_rate": (-500.0, 500.0),
        "natural_population_growth_rate": (-8.0, 8.0),
        "population_growth_rate": (-8.0, 8.0),
    }
    if column in bounds:
        low, high = bounds[column]
        return float(np.clip(value, low, high))
    if column.startswith("age_") or column in {"pop", "population_density"}:
        return float(max(0.0, value))
    return float(value)


def _projection_models(country_df: pd.DataFrame) -> dict[str, tuple[float, float] | None]:
    models = {}
    for column in PROJECTED_COLUMNS:
        if column not in country_df.columns:
            continue
        series = (
            country_df[["year", column]]
            .dropna()
            .sort_values("year")
            .tail(PROJECTION_WINDOW)
        )
        if series.empty:
            models[column] = None
        elif len(series) == 1:
            models[column] = (0.0, float(series[column].iloc[-1]))
        else:
            slope, intercept = np.polyfit(
                series["year"].to_numpy(dtype=float),
                series[column].to_numpy(dtype=float),
                1,
            )
            models[column] = (float(slope), float(intercept))
    return models


def add_projection_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "is_predicted" in df.columns and df["is_predicted"].any():
        return df
    projection_years = range(ACTUAL_MAX_YEAR + 1, PROJECTION_END_YEAR + 1)
    if ACTUAL_MAX_YEAR >= PROJECTION_END_YEAR:
        df = df.copy()
        df["is_predicted"] = False
        return df

    actual = df.copy()
    actual["is_predicted"] = False
    projected_rows = []

    for _, country_df in actual.groupby("iso_alpha", dropna=False):
        country_df = country_df.sort_values("year")
        latest = country_df[country_df["year"].eq(ACTUAL_MAX_YEAR)]
        if latest.empty:
            latest = country_df.tail(1)
        if latest.empty:
            continue
        template = latest.iloc[-1].copy()
        models = _projection_models(country_df)

        for year in projection_years:
            row = template.copy()
            row["year"] = year
            row["is_predicted"] = True
            for column in PROJECTED_COLUMNS:
                if column in row.index:
                    model = models.get(column)
                    row[column] = (
                        np.nan
                        if model is None
                        else _clip_projection(column, model[0] * year + model[1])
                    )
            projected_rows.append(row)

    if not projected_rows:
        return actual
    projected = pd.DataFrame(projected_rows)
    return pd.concat([actual, projected], ignore_index=True)


df_full = add_projection_rows(df_full)
df_countries = df_full[df_full["is_country"]].copy()
df_world = df_full[df_full["iso_alpha"].eq("WORLD")].copy()
min_year = int(df_full["year"].min())
max_year = int(df_full["year"].max())
VALID_ISOS = set(df_countries["iso_alpha"].dropna().unique())
FALLBACK_PALETTE = [
    "#a78bfa",
    "#34d399",
    "#fbbf24",
    "#f472b6",
    "#60a5fa",
    "#fb923c",
    "#2dd4bf",
    "#e879f9",
]


# --- Load Conflict History ---
history_db = {}
history_path = "./data/historical_events.json"
if os.path.exists(history_path):
    with open(history_path, "r", encoding="utf-8") as f:
        history_db = json.load(f)


def country_name(iso: str) -> str:
    if iso in COUNTRY_META:
        return COUNTRY_META[iso]["name"]
    rows = df_countries[df_countries["iso_alpha"].eq(iso)]
    return iso if rows.empty else rows["country"].iloc[0]


def line_color(iso: str, idx: int) -> str:
    meta = COUNTRY_META.get(iso)
    return meta["color"] if meta else FALLBACK_PALETTE[idx % len(FALLBACK_PALETTE)]


def story_from_indicator(indicator: str | None) -> str | None:
    for story_id, config in STORY_CONFIGS.items():
        if indicator == config["indicator"]:
            return story_id
    return None


def story_choices(story_id: str | None) -> dict[str, str]:
    if story_id not in STORY_CONFIGS:
        return {}
    defaults = STORY_CONFIGS[story_id]["isos"]
    country_rows = (
        df_countries[["iso_alpha", "country"]]
        .dropna()
        .drop_duplicates("iso_alpha")
        .sort_values("country")
    )
    choices = {iso: country_name(iso) for iso in defaults}
    for _, row in country_rows.iterrows():
        iso = row["iso_alpha"]
        if iso not in choices:
            choices[iso] = row["country"]
    return choices


def three_stop_colors(
    values: pd.Series,
    vmin: float,
    vmax: float,
    low: tuple[int, int, int],
    mid: tuple[int, int, int],
    high: tuple[int, int, int],
) -> np.ndarray:
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    colors = np.tile(np.array([58, 65, 78], dtype=float), (len(arr), 1))
    mask = np.isfinite(arr)
    if not mask.any():
        return colors.astype(int)

    t = (np.clip(arr[mask], vmin, vmax) - vmin) / (vmax - vmin)
    low_arr = np.array(low, dtype=float)
    mid_arr = np.array(mid, dtype=float)
    high_arr = np.array(high, dtype=float)

    valid_colors = np.empty((len(t), 3), dtype=float)
    first_half = t < 0.5
    valid_colors[first_half] = low_arr + (mid_arr - low_arr) * (t[first_half] * 2)[:, None]
    valid_colors[~first_half] = mid_arr + (high_arr - mid_arr) * ((t[~first_half] - 0.5) * 2)[:, None]
    colors[mask] = valid_colors
    return colors.astype(int)


def net_migration_colors(values: pd.Series) -> np.ndarray:
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    colors = np.tile(np.array([22, 28, 52], dtype=float), (len(arr), 1))
    mask = np.isfinite(arr)
    if not mask.any():
        return colors.astype(int)

    neutral = np.array([22, 28, 52], dtype=float)
    red = np.array([240, 40, 60], dtype=float)
    cyan = np.array([0, 210, 255], dtype=float)
    vals = arr[mask]
    valid_colors = np.empty((len(vals), 3), dtype=float)

    negative = vals < 0
    neg_t = np.clip(np.abs(vals[negative]) / 100, 0, 1)
    pos_t = np.clip(vals[~negative] / 50, 0, 1)
    valid_colors[negative] = neutral + (red - neutral) * neg_t[:, None]
    valid_colors[~negative] = neutral + (cyan - neutral) * pos_t[:, None]
    colors[mask] = valid_colors
    return colors.astype(int)


def fertility_colors(values: pd.Series) -> np.ndarray:
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    colors = np.tile(np.array([58, 65, 78], dtype=float), (len(arr), 1))
    mask = np.isfinite(arr)
    if not mask.any():
        return colors.astype(int)

    low = np.array([239, 68, 68], dtype=float)
    replacement = np.array([148, 163, 184], dtype=float)
    high = np.array([16, 217, 122], dtype=float)
    vals = arr[mask]
    valid_colors = np.empty((len(vals), 3), dtype=float)

    below = vals < 2.1
    below_t = np.clip((vals[below] - 0.7) / (2.1 - 0.7), 0, 1)
    above_t = np.clip((vals[~below] - 2.1) / (5.5 - 2.1), 0, 1)
    valid_colors[below] = low + (replacement - low) * below_t[:, None]
    valid_colors[~below] = replacement + (high - replacement) * above_t[:, None]
    colors[mask] = valid_colors
    return colors.astype(int)


def build_map_payload(df_year: pd.DataFrame, indicator: str) -> list[dict]:
    config = INDICATOR_CONFIG[indicator]
    payload = df_year.copy()
    values = payload[config["col"]]

    if indicator == "net_migration_rate":
        colors = net_migration_colors(values)
    elif indicator == "fertility_rate":
        colors = fertility_colors(values)
    elif indicator == "life_expectancy":
        colors = three_stop_colors(values, 20, 85, (239, 68, 68), (251, 191, 36), (16, 217, 122))
    elif indicator == "child_mortality":
        colors = three_stop_colors(values, 0, 35, (16, 217, 122), (251, 191, 36), (239, 68, 68))
    else:
        colors = three_stop_colors(values, 5, 18, (16, 217, 122), (251, 191, 36), (239, 68, 68))

    payload["raw_value"] = values
    payload["color_r"] = colors[:, 0]
    payload["color_g"] = colors[:, 1]
    payload["color_b"] = colors[:, 2]
    payload["elevation"] = 0

    has_pred = "is_predicted" in payload.columns
    cols = [
        "country",
        "iso_alpha",
        "longitude",
        "latitude",
        "elevation",
        "color_r",
        "color_g",
        "color_b",
        "pop",
        "raw_value",
        "is_spotlight",
    ]
    if has_pred:
        cols.append("is_predicted")
    payload = payload[cols]
    payload = payload.astype(object).where(pd.notna(payload), None)
    return payload.to_dict(orient="records")


print("Precomputing DeckGL color payloads from real OWID data...")
precomputed_payloads = {indicator: {} for indicator in INDICATOR_CONFIG}
for year in range(min_year, max_year + 1):
    df_year = df_countries[df_countries["year"].eq(year)].copy()
    for indicator in INDICATOR_CONFIG:
        precomputed_payloads[indicator][year] = build_map_payload(df_year, indicator)
print("Finished precomputing payloads.")


def story_intro(title: str, *paragraphs: str):
    return ui.div(
        ui.h3(title, class_="story-title"),
        *[ui.p(text, class_="story-copy") for text in paragraphs],
        class_="story-panel",
    )


# --- Dashboard UI Definition ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.p(
            "Use the migration and fertility lenses to turn the globe into a story view.",
            class_="sidebar-caption",
        ),
        ui.tags.button(
            ui.HTML(
                '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
                'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
                'style="margin-right:4px;"><circle cx="12" cy="12" r="5"/>'
                '<line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>'
                '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
                '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
                '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>'
                '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
                '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg> Light mode'
            ),
            id="theme-toggle-btn",
            class_="theme-toggle-btn",
        ),
        ui.input_checkbox(
            "show_projections",
            "Show ML projections to 2030",
            value=False,
        ),
        ui.input_slider(
            "timeline_year",
            "Select Year",
            min=min_year,
            max=ACTUAL_MAX_YEAR,
            value=ACTUAL_MAX_YEAR,
            step=1,
            animate=ui.AnimationOptions(loop=False, interval=260),
            sep="",
        ),
        ui.input_select(
            "indicator",
            "Globe Lens",
            choices={
                "net_migration_rate": "★ Migration Rate",
                "fertility_rate": "★ Fertility Rate",
                "life_expectancy": "Life Expectancy",
                "child_mortality": "Child Mortality",
                "death_rate": "Death Rate",
            },
            selected="net_migration_rate",
        ),
        ui.output_ui("open_story_control"),
        ui.hr(),
        ui.output_ui("indicator_exposition"),
        width=400,
        open="desktop",
    ),
    ui.head_content(
        ui.tags.script(src="https://unpkg.com/deck.gl@8.9.0/dist.min.js"),
        ui.include_css("www/style.css"),
        ui.include_css("www/deep_dive.css"),
    ),
    ui.include_js("www/deck_map.js"),
    ui.div(
        ui.div(
            ui.div(id="deck-map-container", style="width: 100%; height: 100%;"),
            ui.tags.button(
                ui.HTML(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
                    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
                    'style="margin-right: 6px;"><polygon points="3 6 9 3 15 6 21 3 '
                    '21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" '
                    'x2="9" y2="18"></line><line x1="15" y1="6" x2="15" '
                    'y2="21"></line></svg> 2D Map'
                ),
                id="view-toggle-btn",
                class_="view-toggle-btn",
            ),
            ui.div(
                ui.div(
                    ui.output_ui("deep_dive_title"),
                    ui.input_action_button("close_deep_dive", "x", class_="deep-dive-close"),
                    class_="deep-dive-header",
                ),
                ui.output_ui("deep_dive_year_text"),
                ui.div(output_widget("deep_dive_plot"), class_="deep-dive-plot"),
                ui.output_ui("deep_dive_history_text"),
                class_="deep-dive-panel",
            ),
            class_="story-globe-pane",
        ),
        ui.div(
            ui.div(
                ui.output_ui("story_dashboard_header_text"),
                ui.input_action_button("close_story_panel", "Close", class_="story-panel-close"),
                class_="story-dashboard-header",
            ),
            ui.panel_conditional(
                "input.indicator == 'net_migration_rate'",
                ui.div(
                    story_intro(
                        "People Flee, Host States Absorb",
                        "Syria and Venezuela mark the origin shocks. Turkey, Lebanon, Jordan, Colombia, and Peru show how displacement pressure lands unevenly across nearby hosts.",
                        "The host-pressure chart uses OWID net migration rate as a per-capita inflow proxy, not bilateral refugee registry counts.",
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch corridor-origin"), " Conflict origin"),
                        ui.span(ui.span(class_="corridor-swatch corridor-host"), " Refugee-hosting destination"),
                        class_="corridor-legend",
                    ),
                    ui.card(
                        ui.card_header("1. Net Migration Shockwaves"),
                        ui.div(
                            ui.input_selectize(
                                "migration_story_countries",
                                "Countries in this storyline",
                                choices=story_choices("migration"),
                                selected=STORY_CONFIGS["migration"]["isos"],
                                multiple=True,
                            ),
                            ui.input_slider(
                                "migration_year_window",
                                "Migration brush window",
                                min=1990,
                                max=2022,
                                value=(2011, 2022),
                                step=1,
                                sep="",
                            ),
                            class_="figure-controls figure-controls-two",
                        ),
                        ui.div(output_widget("migration_rate_lines"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("2. Peak Historical Immigration Pressure (Per 1,000 Inhabitants)"),
                        ui.div(output_widget("migration_burden_bars"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("3. Age Structure Shift"),
                        ui.div(
                            ui.input_select(
                                "migration_structure_country",
                                "Population structure country",
                                choices=REFUGEE_COUNTRY_CHOICES,
                                selected="SYR",
                            ),
                            class_="figure-controls",
                        ),
                        ui.div(output_widget("migration_population_structure"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("4. ML Forecast to 2030 With Confidence Ribbon"),
                        ui.div(
                            ui.input_select(
                                "migration_forecast_country",
                                "Forecast country",
                                choices=REFUGEE_COUNTRY_CHOICES,
                                selected="SYR",
                            ),
                            ui.input_checkbox("forecast_damped", "Damped forecast trend", value=True),
                            class_="figure-controls figure-controls-two",
                        ),
                        ui.div(output_widget("migration_forecast_chart"), class_="story-plot-slot"),
                    ),
                    class_="story-dashboard-body",
                ),
            ),
            ui.panel_conditional(
                "input.indicator == 'fertility_rate'",
                ui.div(
                    story_intro(
                        "Below Replacement, Then Older",
                        "South Korea, Taiwan, Japan, and China sit far below the 2.1 replacement benchmark. Niger, Chad, and Mali keep the opposite side visible so the cliff is not just a local story.",
                        "The scatter uses population density, life expectancy, child mortality, or growth as available OWID development proxies.",
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch fertility-low"), " Ultra-low fertility"),
                        ui.span(ui.span(class_="corridor-swatch fertility-replacement"), " Replacement 2.1"),
                        ui.span(ui.span(class_="corridor-swatch fertility-high"), " High-fertility contrast"),
                        class_="corridor-legend",
                    ),
                    ui.card(
                        ui.card_header("1. Fertility vs Replacement and Aging"),
                        ui.div(
                            ui.input_selectize(
                                "fertility_story_countries",
                                "Countries in this storyline",
                                choices=story_choices("fertility"),
                                selected=STORY_CONFIGS["fertility"]["isos"],
                                multiple=True,
                            ),
                            class_="figure-controls",
                        ),
                        ui.div(output_widget("fertility_replacement_lines"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("2. Age Structure Shift"),
                        ui.div(
                            ui.input_select(
                                "fertility_structure_country",
                                "Population structure country",
                                choices=FERTILITY_COUNTRY_CHOICES,
                                selected="KOR",
                            ),
                            class_="figure-controls",
                        ),
                        ui.div(output_widget("fertility_population_structure"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("3. Fertility vs Development Proxy"),
                        ui.div(
                            ui.input_select(
                                "scatter_x_metric",
                                "Scatter x-axis metric",
                                choices=SOCIOECONOMIC_METRICS,
                                selected="population_density",
                            ),
                            class_="figure-controls",
                        ),
                        ui.div(output_widget("fertility_socioeconomic_scatter"), class_="story-plot-slot"),
                    ),
                    ui.card(
                        ui.card_header("4. K-Means Demographic Clusters"),
                        ui.div(
                            ui.input_slider(
                                "cluster_count",
                                "K-Means clusters",
                                min=2,
                                max=8,
                                value=4,
                                step=1,
                            ),
                            class_="figure-controls",
                        ),
                        ui.div(output_widget("fertility_kmeans_clusters"), class_="story-plot-slot"),
                    ),
                    class_="story-dashboard-body",
                ),
            ),
            class_="story-dashboard-panel",
        ),
        id="story-stage",
        class_="story-stage",
    ),
    title="Where People Move, Where Populations Fade",
)


def server(input, output, session):
    selected_country = reactive.Value(None)
    story_panel_open = reactive.Value(False)
    theme = reactive.Value("dark")

    @reactive.Calc
    def plotly_template() -> str:
        return "plotly_dark" if theme.get() == "dark" else "plotly_white"

    def _chart_theme() -> dict:
        """Return theme-aware style dict for Plotly chart elements."""
        dark = theme.get() == "dark"
        return {
            "template": "plotly_dark" if dark else "plotly_white",
            "gridcolor": "rgba(255,255,255,0.07)" if dark else "rgba(0,0,0,0.08)",
            "hover_bg": "rgba(15,23,42,0.96)" if dark else "rgba(255,255,255,0.96)",
            "hover_font": "#f8fafc" if dark else "#0f172a",
            "hover_border": "#818cf8" if dark else "#6366f1",
            "legend_bg": "rgba(15,23,42,0.78)" if dark else "rgba(255,255,255,0.85)",
            "legend_font": "#f8fafc" if dark else "#0f172a",
            "text_primary": "#f0f4ff" if dark else "#0f172a",
            "text_secondary": "#94a3b8" if dark else "#475569",
        }

    @reactive.Effect
    @reactive.event(input.current_theme)
    def handle_theme_change():
        theme.set(input.current_theme())

    @reactive.Calc
    def has_predictions() -> bool:
        return "is_predicted" in df_full.columns and df_full["is_predicted"].any()

    @reactive.Calc
    def effective_max_year() -> int:
        if has_predictions() and input.show_projections():
            return max_year
        return ACTUAL_MAX_YEAR

    def visible_time_series(frame: pd.DataFrame) -> pd.DataFrame:
        if has_predictions() and input.show_projections():
            return frame
        if "is_predicted" in frame.columns:
            return frame[frame["is_predicted"] == False]
        return frame[frame["year"].le(ACTUAL_MAX_YEAR)]

    def chart_year() -> int:
        return int(np.clip(input.timeline_year(), min_year, effective_max_year()))

    def selected_from_input(input_id: str, default: str, allowed: list[str]) -> str:
        try:
            value = getattr(input, input_id)()
        except Exception:
            value = default
        return value if value in allowed else default

    def selected_story_country(input_id: str, fallback: str) -> str:
        allowed = selected_story_isos()
        default = fallback if fallback in allowed else (allowed[0] if allowed else fallback)
        return selected_from_input(input_id, default, allowed or [fallback])

    def selected_metric() -> str:
        try:
            metric = input.scatter_x_metric()
        except Exception:
            metric = "population_density"
        return metric if metric in SOCIOECONOMIC_METRICS else "population_density"

    def age_structure(iso: str, year: int, include_projected: bool = True) -> pd.DataFrame:
        frame = df_countries[df_countries["iso_alpha"].eq(iso)].copy()
        if not include_projected:
            frame = frame[frame["is_predicted"] == False]
        else:
            frame = visible_time_series(frame)
        if frame.empty:
            return pd.DataFrame(columns=["age_group", "count", "share"])

        target_year = int(np.clip(year, int(frame["year"].min()), int(frame["year"].max())))
        exact = frame[frame["year"].eq(target_year)]
        if exact.empty:
            exact = frame.loc[[(frame["year"] - target_year).abs().idxmin()]]
        row = exact.iloc[0]
        counts = []
        for column, _ in AGE_GROUPS:
            value = pd.to_numeric(row.get(column, np.nan), errors="coerce")
            counts.append(float(value) if np.isfinite(value) else 0.0)
        counts = np.array(counts)
        total = counts.sum()
        shares = counts / total * 100 if total > 0 else np.zeros(len(counts))
        return pd.DataFrame(
            {
                "age_group": [label for _, label in AGE_GROUPS],
                "count": counts,
                "share": shares,
                "year": int(row["year"]),
                "country": country_name(iso),
            }
        )

    def _forecast_frame(iso: str, col: str, damped: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        train = df_countries[
            df_countries["iso_alpha"].eq(iso)
            & df_countries["year"].between(1990, 2022)
            & (df_countries["is_predicted"] == False)
            & df_countries[col].notna()
        ][["year", col]].sort_values("year")
        if len(train) < 5:
            return train, pd.DataFrame(columns=["year", "mean", "lower", "upper"])

        years = list(range(2023, 2031))
        values = train[col].to_numpy(dtype=float)
        mean = None
        sigma = float(np.nanstd(values)) * 0.25

        if ExponentialSmoothing is not None:
            try:
                model = ExponentialSmoothing(
                    values,
                    trend="add",
                    damped_trend=bool(damped),
                    initialization_method="estimated",
                ).fit(optimized=True)
                mean = np.asarray(model.forecast(len(years)), dtype=float)
                residuals = values - np.asarray(model.fittedvalues, dtype=float)
                sigma = float(np.nanstd(residuals))
            except Exception:
                mean = None

        if mean is None:
            slope, intercept = np.polyfit(train["year"].to_numpy(dtype=float), values, 1)
            mean = slope * np.array(years, dtype=float) + intercept
            residuals = values - (slope * train["year"].to_numpy(dtype=float) + intercept)
            sigma = float(np.nanstd(residuals))

        if not np.isfinite(sigma) or sigma <= 0:
            sigma = max(1.0, float(np.nanstd(values)) * 0.15)
        mean = np.array([_clip_projection(col, value) for value in mean])
        step_scale = np.sqrt(1 + np.arange(1, len(years) + 1) / max(len(train), 1))
        band = 1.96 * sigma * step_scale
        forecast = pd.DataFrame(
            {
                "year": years,
                "mean": mean,
                "lower": mean - band,
                "upper": mean + band,
            }
        )
        return train, forecast

    def _role_for_iso(iso: str) -> str:
        if iso in REFUGEE_ORIGINS:
            return "origin"
        if iso in REFUGEE_HOSTS:
            return "host"
        if iso in FERTILITY_COLLAPSE:
            return "collapse"
        if iso in FERTILITY_SCALE_SHIFT:
            return "scale"
        if iso in FERTILITY_HIGH_GROWTH:
            return "high"
        return "other"

    # Shared reactive data paths: charts below consume these single filtered frames.
    @reactive.Calc
    def migration_brush_window() -> tuple[int, int]:
        try:
            raw = input.migration_year_window()
        except Exception:
            raw = (2011, 2022)
        if raw is None:
            return (2011, 2022)
        start, end = int(raw[0]), int(raw[1])
        start = int(np.clip(start, 1990, 2022))
        end = int(np.clip(end, 1990, 2022))
        return (min(start, end), max(start, end))

    @reactive.Calc
    def migration_story_frame() -> pd.DataFrame:
        isos = selected_story_isos()
        return df_countries[
            df_countries["iso_alpha"].isin(isos)
            & df_countries["year"].between(1990, 2022)
            & (df_countries["is_predicted"] == False)
        ].copy()

    @reactive.Calc
    def migration_window_frame() -> pd.DataFrame:
        start, end = migration_brush_window()
        frame = migration_story_frame()
        return frame[frame["year"].between(start, end)].copy()

    @reactive.Calc
    def migration_forecast_data() -> tuple[pd.DataFrame, pd.DataFrame, str]:
        iso = selected_story_country("migration_forecast_country", "SYR")
        try:
            damped = bool(input.forecast_damped())
        except Exception:
            damped = True
        hist, forecast = _forecast_frame(iso, "net_migration_rate", damped)
        return hist, forecast, iso

    @reactive.Calc
    def fertility_story_frame() -> pd.DataFrame:
        isos = selected_story_isos()
        frame = visible_time_series(df_countries)
        return frame[frame["iso_alpha"].isin(isos)].copy()

    @reactive.Calc
    def global_year_frame() -> pd.DataFrame:
        frame = visible_time_series(df_countries)
        year = chart_year()
        return frame[
            frame["year"].eq(year)
            & frame["is_country"]
            & frame["fertility_rate"].notna()
            & frame["pop"].fillna(0).gt(500_000)
        ].copy()

    @reactive.Calc
    def fertility_scatter_frame() -> pd.DataFrame:
        metric = selected_metric()
        frame = global_year_frame()
        frame = frame[frame[metric].notna()].copy()
        frame["story_role"] = frame["iso_alpha"].map(_role_for_iso)
        return frame

    @reactive.Calc
    def kmeans_cluster_frame() -> pd.DataFrame:
        frame = global_year_frame().copy()
        age_total = frame[[column for column, _ in AGE_GROUPS]].sum(axis=1).replace(0, np.nan)
        frame["child_share"] = (frame["age_0_4"] + frame["age_5_14"]) / age_total * 100
        frame["working_share"] = (frame["age_15_24"] + frame["age_25_64"]) / age_total * 100
        frame["elder_share"] = frame["age_65_plus"] / age_total * 100
        feature_cols = [
            "fertility_rate",
            "lifeExp",
            "population_growth_rate",
            "natural_population_growth_rate",
            "birth_rate",
            "death_rate",
            "child_share",
            "working_share",
            "elder_share",
        ]
        frame = frame.dropna(subset=feature_cols).copy()
        if frame.empty:
            return pd.DataFrame()

        x = frame[feature_cols].to_numpy(dtype=float)
        if StandardScaler is not None:
            x_scaled = StandardScaler().fit_transform(x)
        else:
            x_scaled = (x - x.mean(axis=0)) / np.where(x.std(axis=0) == 0, 1, x.std(axis=0))

        if PCA is not None:
            coords = PCA(n_components=2, random_state=7).fit_transform(x_scaled)
        else:
            _, _, vt = np.linalg.svd(x_scaled, full_matrices=False)
            coords = x_scaled @ vt[:2].T

        try:
            requested_k = int(input.cluster_count())
        except Exception:
            requested_k = 4
        k = int(np.clip(requested_k, 2, min(8, len(frame))))
        if KMeans is not None:
            labels = KMeans(n_clusters=k, random_state=7, n_init=10).fit_predict(x_scaled)
        else:
            order = np.argsort(coords[:, 0])
            labels = np.zeros(len(frame), dtype=int)
            labels[order] = np.floor(np.linspace(0, k - 1, len(frame))).astype(int)

        frame["cluster"] = labels.astype(str)
        frame["pca_x"] = coords[:, 0]
        frame["pca_y"] = coords[:, 1]
        frame["story_role"] = frame["iso_alpha"].map(_role_for_iso)
        return frame

    @reactive.Effect
    @reactive.event(input.show_projections)
    def _sync_slider_range():
        next_max = effective_max_year()
        if input.timeline_year() > next_max:
            ui.update_slider("timeline_year", max=next_max, value=next_max)
        else:
            ui.update_slider("timeline_year", max=next_max)

    @reactive.Calc
    def active_story() -> str | None:
        return story_from_indicator(input.indicator())

    @reactive.Calc
    def open_story_id() -> str | None:
        story_id = active_story()
        if story_panel_open.get() and story_id in STORY_CONFIGS:
            return story_id
        return None

    @reactive.Calc
    def selected_story_isos() -> list[str]:
        story_id = open_story_id() or active_story()
        if story_id not in STORY_CONFIGS:
            return []

        defaults = STORY_CONFIGS[story_id]["isos"]
        input_id = "migration_story_countries" if story_id == "migration" else "fertility_story_countries"
        try:
            selected = getattr(input, input_id)()
        except Exception:
            selected = None
        if selected is None:
            return defaults
        if isinstance(selected, str):
            selected = [selected]
        selected = [iso for iso in selected if iso in VALID_ISOS]
        return selected or defaults

    @reactive.Effect
    def sync_story_country_dropdowns():
        story_id = open_story_id()
        if story_id not in STORY_CONFIGS:
            return

        isos = selected_story_isos()
        if not isos:
            return
        choices = {iso: country_name(iso) for iso in isos}

        def current_or_first(input_id: str) -> str:
            try:
                current = getattr(input, input_id)()
            except Exception:
                current = None
            return current if current in choices else isos[0]

        if story_id == "migration":
            ui.update_select(
                "migration_structure_country",
                choices=choices,
                selected=current_or_first("migration_structure_country"),
            )
            ui.update_select(
                "migration_forecast_country",
                choices=choices,
                selected=current_or_first("migration_forecast_country"),
            )
        elif story_id == "fertility":
            ui.update_select(
                "fertility_structure_country",
                choices=choices,
                selected=current_or_first("fertility_structure_country"),
            )

    @render.ui
    def open_story_control():
        story_id = active_story()
        if story_id not in STORY_CONFIGS:
            return None
        label = "See story charts about this lens"
        return ui.div(
            ui.input_action_button("open_story", label, class_="story-open-button"),
            class_="story-sidebar-block",
        )

    @reactive.Effect
    @reactive.event(input.indicator)
    def handle_indicator_change():
        story_panel_open.set(False)

    @reactive.Effect
    @reactive.event(input.open_story)
    def handle_open_story():
        if active_story() in STORY_CONFIGS:
            story_panel_open.set(True)

    @reactive.Effect
    @reactive.event(input.close_story_panel)
    def handle_close_story_panel():
        story_panel_open.set(False)

    @render.ui
    def story_dashboard_header_text():
        story_id = open_story_id()
        if story_id not in STORY_CONFIGS:
            return ui.div(
                ui.span("Global overview", class_="story-dashboard-eyebrow"),
                ui.h3("Choose a Story Lens", class_="story-dashboard-title"),
                ui.p(
                    "Migration and fertility are the highlighted lenses. Open either story to keep the globe in view while the dashboard slides beside it.",
                    class_="story-dashboard-copy",
                ),
            )

        config = STORY_CONFIGS[story_id]
        return ui.div(
            ui.span(config["eyebrow"], class_="story-dashboard-eyebrow"),
            ui.h3(config["title"], class_="story-dashboard-title"),
            ui.p(config["copy"], class_="story-dashboard-copy"),
        )

    @reactive.Effect
    @reactive.event(input.selected_country_iso)
    def handle_country_click():
        iso = input.selected_country_iso()
        if iso:
            selected_country.set(iso.upper())

    @reactive.Effect
    @reactive.event(input.close_deep_dive)
    async def handle_close_deep_dive():
        selected_country.set(None)
        await session.send_custom_message("panel_closed", {})

    @render.ui
    def deep_dive_title():
        iso = selected_country.get()
        if not iso:
            return None

        country_df = df_countries[df_countries["iso_alpha"].eq(iso)]
        if country_df.empty:
            return None

        country = country_df["country"].iloc[0]
        return ui.h4(country, class_="deep-dive-title")

    @reactive.Effect
    async def sync_deep_dive_visibility():
        await session.send_custom_message(
            "deep_dive_visibility",
            {"open": bool(selected_country.get())},
        )

    @render.ui
    def deep_dive_year_text():
        iso = selected_country.get()
        if not iso:
            return None
        country_df = df_countries[df_countries["iso_alpha"].eq(iso)]
        if country_df.empty:
            return None
        year = input.timeline_year()
        config = INDICATOR_CONFIG[input.indicator()]
        return ui.div(
            f"{config['label']} trend for {country_df['country'].iloc[0]}. "
            f"The marker shows the selected year ({year}).",
            class_="deep-dive-content",
        )

    @render.ui
    def deep_dive_history_text():
        iso = selected_country.get()
        if not iso or iso not in history_db:
            return None

        year = input.timeline_year()
        current_period = None
        for period in history_db[iso]:
            if period["start"] <= year <= period["end"]:
                current_period = period
                break

        if not current_period:
            return None

        return ui.div(
            ui.div(
                ui.span(
                    f"Period {current_period['start']}-{current_period['end']} Context:",
                    class_="history-period-label",
                ),
                ui.span(current_period["period"], class_="history-period-title"),
                class_="history-header-block",
            ),
            ui.p(current_period["details"], class_="history-details"),
            ui.div(ui.span(current_period["source"], class_="history-source"), class_="history-footer"),
            class_="vn-history-box",
        )

    # ── Deep Dive FigureWidget (pre-allocated, never recreated) ──────
    _dd_fig = go.FigureWidget()
    _dd_fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=18, b=36),
        height=220,
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.96)",
            bordercolor="#818cf8",
            font=dict(color="#f8fafc", size=12),
        ),
    )
    _dd_fig.update_xaxes(title_text="Year", gridcolor="rgba(255,255,255,0.07)")
    _dd_fig.update_yaxes(title_text="", gridcolor="rgba(255,255,255,0.07)")
    # Pre-allocate traces: [0] hist, [1] pred, [2] bridge, [3] vline
    _dd_fig.add_scatter(x=[], y=[], mode="lines", line=dict(color="#818cf8", width=2.5), name="")
    _dd_fig.add_scatter(x=[], y=[], mode="lines", line=dict(color="#818cf8", width=2, dash="dash"), name="")
    _dd_fig.add_scatter(x=[], y=[], mode="lines", line=dict(color="#818cf8", width=1.5, dash="dot"), showlegend=False, hoverinfo="skip")
    _dd_fig.add_vline(x=2023, line_width=2, line_dash="dash", line_color="#ef4444")

    @render_widget
    def deep_dive_plot():
        return _dd_fig

    @reactive.Effect
    def _update_deep_dive_data():
        """Full update — country, indicator, or projection toggle changed."""
        iso = selected_country.get()
        if not iso:
            with _dd_fig.batch_update():
                _dd_fig.data[0].x = []
                _dd_fig.data[0].y = []
                _dd_fig.data[1].x = []
                _dd_fig.data[1].y = []
                _dd_fig.data[2].x = []
                _dd_fig.data[2].y = []
            return

        indicator = input.indicator()
        config = INDICATOR_CONFIG[indicator]
        country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
        if country_df.empty:
            return

        has_pred = has_predictions() and input.show_projections()
        if has_pred and "is_predicted" in country_df.columns:
            hist = country_df[country_df["is_predicted"] == False]
            pred = country_df[country_df["is_predicted"] == True]
        else:
            hist = visible_time_series(country_df)
            pred = pd.DataFrame()

        with _dd_fig.batch_update():
            # Trace 0: historical
            if not hist.empty:
                _dd_fig.data[0].x = hist["year"].tolist()
                _dd_fig.data[0].y = hist[config["col"]].tolist()
            else:
                _dd_fig.data[0].x = []
                _dd_fig.data[0].y = []

            # Trace 1: predicted
            if not pred.empty:
                _dd_fig.data[1].x = pred["year"].tolist()
                _dd_fig.data[1].y = pred[config["col"]].tolist()
            else:
                _dd_fig.data[1].x = []
                _dd_fig.data[1].y = []

            # Trace 2: bridge
            if not hist.empty and not pred.empty:
                _dd_fig.data[2].x = [int(hist["year"].iloc[-1]), int(pred["year"].iloc[0])]
                _dd_fig.data[2].y = [float(hist[config["col"]].iloc[-1]), float(pred[config["col"]].iloc[0])]
            else:
                _dd_fig.data[2].x = []
                _dd_fig.data[2].y = []

            # Update all theme-dependent properties
            ct = _chart_theme()
            _dd_fig.layout.template = ct["template"]
            _dd_fig.layout.yaxis.title.text = config["unit"]
            _dd_fig.layout.yaxis.gridcolor = ct["gridcolor"]
            _dd_fig.layout.xaxis.gridcolor = ct["gridcolor"]
            _dd_fig.layout.hoverlabel.bgcolor = ct["hover_bg"]
            _dd_fig.layout.hoverlabel.bordercolor = ct["hover_border"]
            _dd_fig.layout.hoverlabel.font.color = ct["hover_font"]

    @reactive.Effect
    def _update_deep_dive_vline():
        """Lightweight update — only move the vertical year marker."""
        year = input.timeline_year()
        if len(_dd_fig.layout.shapes) > 0:
            with _dd_fig.batch_update():
                _dd_fig.layout.shapes[0].x0 = year
                _dd_fig.layout.shapes[0].x1 = year

    def legend_bar(gradient: str, left: str, middle: str, right: str) -> ui.TagList:
        return ui.TagList(
            ui.div(
                style=(
                    "height: 12px; border-radius: 6px; "
                    f"background: {gradient}; "
                    "margin-bottom: 8px; border: 1px solid var(--border-accent);"
                )
            ),
            ui.div(
                ui.span(left, style="font-size: 0.8rem; color: var(--text-primary); font-weight: 600;"),
                ui.span(
                    middle,
                    style=(
                        "font-size: 0.8rem; color: var(--text-secondary); font-weight: 600; "
                        "position: absolute; left: 50%; transform: translateX(-50%);"
                    ),
                ),
                ui.span(right, style="font-size: 0.8rem; color: var(--text-primary); font-weight: 600; float: right;"),
                style="position: relative; overflow: visible; height: 20px;",
            ),
            ui.div(style="margin-bottom: 20px;"),
        )

    @render.ui
    def indicator_exposition():
        indicator = input.indicator()
        if indicator == "net_migration_rate":
            return ui.TagList(
                ui.h4("Lens: Migration Rate", class_="exposition-title"),
                ui.p(
                    "A highlight lens for the story view. Deep red marks net outflow; cyan marks net inflow."
                ),
                ui.h5("Map Legend:"),
                legend_bar(
                    "linear-gradient(to right, #f02840, #161c34, #00d2ff)",
                    "Outflow",
                    "Neutral",
                    "Inflow",
                ),
            )
        if indicator == "fertility_rate":
            return ui.TagList(
                ui.h4("Lens: Fertility Rate", class_="exposition-title"),
                ui.p(
                    "A highlight lens for the story view. Red marks ultra-low fertility; gray marks replacement level near 2.1; green marks high fertility."
                ),
                ui.h5("Map Legend:"),
                legend_bar(
                    "linear-gradient(to right, #ef4444 0%, #94a3b8 38%, #10d97a 100%)",
                    "0.7",
                    "2.1 replacement",
                    "5.5+",
                ),
            )
        if indicator == "life_expectancy":
            return ui.TagList(
                ui.h4("Lens: Life Expectancy", class_="exposition-title"),
                ui.p("Low values mark survival collapse; high values mark long-life societies."),
                ui.h5("Map Legend:"),
                legend_bar(
                    "linear-gradient(to right, #ef4444, #fbbf24, #10d97a)",
                    "20 yrs",
                    "52 yrs",
                    "85 yrs",
                ),
            )
        if indicator == "child_mortality":
            return ui.TagList(
                ui.h4("Lens: Child Mortality", class_="exposition-title"),
                ui.p("Green means low mortality; red means children are dying at elevated rates."),
                ui.h5("Map Legend:"),
                legend_bar(
                    "linear-gradient(to right, #10d97a, #fbbf24, #ef4444)",
                    "0%",
                    "17.5%",
                    "35%+",
                ),
            )
        return ui.TagList(
            ui.h4("Lens: Death Rate", class_="exposition-title"),
            ui.p("Green means low annual mortality; red marks elevated death rates."),
            ui.h5("Map Legend:"),
            legend_bar(
                "linear-gradient(to right, #10d97a, #fbbf24, #ef4444)",
                "5",
                "11.5",
                "18+",
            ),
        )

    @reactive.Effect
    async def send_deck_data():
        year = input.timeline_year()
        indicator = input.indicator()
        payload = precomputed_payloads[indicator][year]
        await session.send_custom_message(
            "update_deck_data",
            {
                "data": payload,
                "indicator": indicator,
            },
        )

    @reactive.Effect
    async def send_group_focus():
        story_id = open_story_id()
        config = STORY_CONFIGS.get(story_id, {})
        is_open = bool(story_id)
        await session.send_custom_message(
            "focus_group",
            {
                "open": is_open,
                "dim": is_open,
                "isos": selected_story_isos() if is_open else [],
                "origins": [iso for iso in config.get("origins", []) if iso in selected_story_isos()],
                "hosts": [iso for iso in config.get("hosts", []) if iso in selected_story_isos()],
                "routes": [],
                "targetState": config.get("target", {"longitude": 0, "latitude": 10, "zoom": 0.85}),
            },
        )

    def add_country_lines(
        fig: go.Figure,
        country_df: pd.DataFrame,
        col: str,
        name: str,
        color: str,
        width: float = 2.7,
        dash_solid: str = "solid",
        dash_pred: str = "dash",
        show_pred: bool = True,
    ) -> None:
        """Add historical (solid) + predicted (dashed) traces for a country."""
        has_pred = has_predictions() and show_pred and input.show_projections()
        if has_pred and "is_predicted" in country_df.columns:
            hist = country_df[country_df["is_predicted"] == False].sort_values("year")
            pred = country_df[country_df["is_predicted"] == True].sort_values("year")
        else:
            hist = visible_time_series(country_df).sort_values("year")
            pred = pd.DataFrame()

        if not hist.empty:
            fig.add_scatter(
                x=hist["year"], y=hist[col],
                mode="lines",
                name=name,
                line=dict(color=color, width=width, dash=dash_solid),
            )
        if not pred.empty:
            fig.add_scatter(
                x=pred["year"], y=pred[col],
                mode="lines",
                name=f"{name} (projected)",
                line=dict(color=color, width=width * 0.75, dash=dash_pred),
                showlegend=True,
            )

    def add_conflict_shading(fig: go.Figure, isos: list[str]) -> None:
        for iso in isos:
            for period in history_db.get(iso, []):
                fig.add_vrect(
                    x0=period["start"],
                    x1=period["end"],
                    fillcolor=COUNTRY_META.get(iso, {}).get("color", "#ef4444"),
                    opacity=0.08,
                    line_width=0,
                    layer="below",
                )

    def apply_story_layout(fig: go.Figure, y_title: str, height: int = 390) -> go.Figure:
        ct = _chart_theme()
        fig.update_layout(
            title=None,
            template=ct["template"],
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=34, r=24, t=76, b=58),
            height=height,
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor=ct["hover_bg"],
                bordercolor=ct["hover_border"],
                font=dict(color=ct["hover_font"], size=12),
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor=ct["legend_bg"],
                bordercolor=ct["gridcolor"],
                borderwidth=1,
                font=dict(color=ct["legend_font"], size=12),
            ),
        )
        fig.update_traces(hoverlabel=dict(bgcolor=ct["hover_bg"], font=dict(color=ct["hover_font"])))
        fig.update_xaxes(title_text="Year", title_standoff=12, gridcolor=ct["gridcolor"])
        fig.update_yaxes(title_text=y_title if y_title else None, gridcolor=ct["gridcolor"])
        return fig

    @render_widget
    def migration_rate_lines():
        if open_story_id() != "migration":
            return go.Figure()
        selected_isos = selected_story_isos()
        fig = go.Figure()
        start, end = migration_brush_window()
        fig.add_vrect(
            x0=start,
            x1=end,
            fillcolor="#818cf8",
            opacity=0.12,
            line_width=0,
            layer="below",
        )
        add_conflict_shading(fig, [iso for iso in selected_isos if iso in MIGRATION_OUTFLOW])

        for idx, iso in enumerate(selected_isos):
            country_df = migration_story_frame()
            country_df = country_df[country_df["iso_alpha"].eq(iso)].sort_values("year")
            if country_df.empty:
                continue
            is_outflow = iso in MIGRATION_OUTFLOW
            fig.add_scatter(
                x=country_df["year"],
                y=country_df["net_migration_rate"],
                mode="lines",
                name=country_name(iso),
                line=dict(
                    color=line_color(iso, idx),
                    width=3 if is_outflow else 2.4,
                    dash="solid" if is_outflow else "dot",
                ),
                hovertemplate="%{x}<br>%{y:+.2f} per 1,000<extra></extra>",
            )

        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#94a3b8")
        year_marker = int(np.clip(chart_year(), 1990, 2022))
        fig.add_vline(x=year_marker, line_width=1.5, line_dash="dash", line_color="#e2e8f0")
        fig = apply_story_layout(fig, "Migrants per 1,000 people", 420)
        ct = _chart_theme()
        if "SYR" in selected_isos:
            fig.add_vline(x=2013, line_width=1.5, line_dash="dash", line_color="#ef4444")
            fig.add_annotation(
                x=2013,
                y=1.03,
                yref="paper",
                text="2013: Syria war displacement",
                showarrow=False,
                font=dict(color=ct["text_primary"], size=11),
                bgcolor=ct["hover_bg"],
                bordercolor=ct["gridcolor"],
                borderwidth=1,
            )
        if "VEN" in selected_isos:
            fig.add_vrect(
                x0=2018,
                x1=2019,
                fillcolor="#f97316",
                opacity=0.12,
                line_width=0,
                layer="below",
            )
            fig.add_annotation(
                x=2018.5,
                y=0.9,
                yref="paper",
                text="2018-19: Venezuela exodus",
                showarrow=False,
                font=dict(color=ct["text_primary"], size=11),
                bgcolor=ct["hover_bg"],
                bordercolor=ct["gridcolor"],
                borderwidth=1,
            )
        fig.update_layout(dragmode="select")
        fig.update_xaxes(range=[1990, 2022])
        return fig

    @render_widget
    def migration_burden_bars():
        if open_story_id() != "migration":
            return go.Figure()
        frame = migration_window_frame()
        selected_isos = selected_story_isos()
        host_like_isos = [iso for iso in selected_isos if iso not in MIGRATION_OUTFLOW]
        if not host_like_isos:
            host_like_isos = selected_isos
        rows = []
        for iso in host_like_isos:
            country_df = frame[frame["iso_alpha"].eq(iso)]
            if country_df.empty:
                continue
            positive = country_df["net_migration_rate"].clip(lower=0)
            idx = positive.idxmax()
            row = country_df.loc[idx]
            rows.append(
                {
                    "country": country_name(iso),
                    "iso": iso,
                    "pressure": float(max(0, row["net_migration_rate"])),
                    "year": int(row["year"]),
                }
            )
        rows = sorted(rows, key=lambda row: row["pressure"])

        fig = go.Figure()
        fig.add_bar(
            y=[row["country"] for row in rows],
            x=[row["pressure"] for row in rows],
            orientation="h",
            marker_color=[line_color(row["iso"], idx) for idx, row in enumerate(rows)],
            text=[f"{row['pressure']:.1f} ({row['year']})" for row in rows],
            textposition="auto",
            hovertemplate="%{y}<br>Peak host-pressure proxy: %{x:.2f} per 1,000<extra></extra>",
        )
        fig = apply_story_layout(fig, "", 360)
        fig.update_layout(showlegend=False, margin=dict(l=32, r=24, t=24, b=54))
        fig.update_xaxes(title_text="Net Migrants per 1,000 Inhabitants")
        fig.update_yaxes(automargin=True)
        return fig

    @render_widget
    def migration_population_structure():
        if open_story_id() != "migration":
            return go.Figure()
        iso = selected_story_country("migration_structure_country", "SYR")
        compare_year = int(np.clip(chart_year(), 1990, 2022))
        baseline = age_structure(iso, 1990, include_projected=False)
        current = age_structure(iso, compare_year, include_projected=False)
        fig = go.Figure()
        fig.add_bar(
            y=baseline["age_group"],
            x=baseline["share"],
            orientation="h",
            name="1990",
            marker_color="rgba(148, 163, 184, 0.58)",
            hovertemplate="1990<br>%{y}: %{x:.1f}%<extra></extra>",
        )
        fig.add_bar(
            y=current["age_group"],
            x=current["share"],
            orientation="h",
            name=str(compare_year),
            marker_color=COUNTRY_META.get(iso, {}).get("color", "#818cf8"),
            hovertemplate=f"{compare_year}<br>%{{y}}: %{{x:.1f}}%<extra></extra>",
        )
        fig = apply_story_layout(fig, f"{country_name(iso)} population share", 360)
        fig.update_layout(barmode="group", margin=dict(l=34, r=24, t=76, b=58))
        fig.update_xaxes(title_text="Share of population (%)")
        fig.update_yaxes(autorange="reversed")
        return fig

    @render_widget
    def migration_forecast_chart():
        if open_story_id() != "migration":
            return go.Figure()
        hist, forecast, iso = migration_forecast_data()
        fig = go.Figure()
        if not hist.empty:
            fig.add_scatter(
                x=hist["year"],
                y=hist["net_migration_rate"],
                mode="lines",
                name="Historical 1990-2022",
                line=dict(color=COUNTRY_META.get(iso, {}).get("color", "#ef4444"), width=3),
                hovertemplate="%{x}<br>%{y:+.2f} per 1,000<extra></extra>",
            )
        if not forecast.empty:
            fig.add_scatter(
                x=list(forecast["year"]) + list(forecast["year"])[::-1],
                y=list(forecast["upper"]) + list(forecast["lower"])[::-1],
                fill="toself",
                fillcolor="rgba(129, 140, 248, 0.18)",
                line=dict(color="rgba(129, 140, 248, 0)"),
                name="95% interval",
                hoverinfo="skip",
            )
            fig.add_scatter(
                x=forecast["year"],
                y=forecast["mean"],
                mode="lines",
                name="Forecast mean",
                line=dict(color="#a5b4fc", width=2.8, dash="dash"),
                hovertemplate="%{x}<br>%{y:+.2f} per 1,000<extra></extra>",
            )
        fig.add_vline(x=2022, line_width=1.5, line_dash="dot", line_color="#e2e8f0")
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#94a3b8")
        fig = apply_story_layout(fig, f"{country_name(iso)} migrants per 1,000", 400)
        fig.update_xaxes(range=[1990, 2030])
        return fig

    @render_widget
    def migration_peak_shocks():
        if open_story_id() != "migration":
            return go.Figure()
        rows = []
        for iso in selected_story_isos():
            country_df = visible_time_series(df_countries[df_countries["iso_alpha"].eq(iso)])
            country_df = country_df[country_df["net_migration_rate"].notna()]
            if country_df.empty:
                continue
            if iso in MIGRATION_OUTFLOW:
                row = country_df.loc[country_df["net_migration_rate"].idxmin()]
                value_label = "Worst outflow"
            elif iso in MIGRATION_INFLOW:
                row = country_df.loc[country_df["net_migration_rate"].idxmax()]
                value_label = "Strongest inflow"
            else:
                min_row = country_df.loc[country_df["net_migration_rate"].idxmin()]
                max_row = country_df.loc[country_df["net_migration_rate"].idxmax()]
                row = (
                    min_row
                    if abs(float(min_row["net_migration_rate"])) >= abs(float(max_row["net_migration_rate"]))
                    else max_row
                )
                value_label = "Largest migration swing"
            rows.append(
                {
                    "country": country_name(iso),
                    "iso": iso,
                    "value": float(row["net_migration_rate"]),
                    "year": int(row["year"]),
                    "type": value_label,
                }
            )

        rows = sorted(rows, key=lambda row: row["value"])
        fig = go.Figure()
        fig.add_bar(
            y=[row["country"] for row in rows],
            x=[row["value"] for row in rows],
            orientation="h",
            marker_color=[
                "#ef4444"
                if row["iso"] in MIGRATION_OUTFLOW
                else ("#22d3ee" if row["iso"] in MIGRATION_INFLOW else "#94a3b8")
                for row in rows
            ],
            text=[f"{row['value']:+.1f} ({row['year']})" for row in rows],
            textposition="auto",
            hovertemplate="%{y}<br>%{x:+.2f} per 1,000<extra></extra>",
        )
        fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="#e2e8f0")
        fig = apply_story_layout(fig, "Net migration rate", 390)
        fig.update_yaxes(automargin=True)
        fig.update_layout(showlegend=False, margin=dict(l=30, r=24, t=24, b=54))
        return fig

    @render_widget
    def fertility_replacement_lines():
        if open_story_id() != "fertility":
            return go.Figure()
        selected_isos = selected_story_isos()
        fig = go.Figure()
        frame = fertility_story_frame()

        if not df_world.empty:
            world = visible_time_series(df_world).sort_values("year")
            fig.add_trace(
                go.Scatter(
                    x=world["year"],
                    y=world["fertility_rate"],
                    mode="lines",
                    name="World fertility",
                    line=dict(color="#e2e8f0", width=2.5, dash="dot"),
                    hovertemplate="%{x}<br>%{y:.2f} children per woman<extra></extra>",
                ),
            )

        for idx, iso in enumerate(selected_isos):
            country_df = frame[frame["iso_alpha"].eq(iso)].sort_values("year")
            if country_df.empty:
                continue
            hist = country_df[country_df["is_predicted"] == False]
            pred = country_df[country_df["is_predicted"] == True]
            fig.add_trace(
                go.Scatter(
                    x=hist["year"],
                    y=hist["fertility_rate"],
                    mode="lines",
                    name=country_name(iso),
                    line=dict(color=line_color(iso, idx), width=2.7),
                    hovertemplate="%{x}<br>%{y:.2f} children per woman<extra></extra>",
                ),
            )
            if not pred.empty:
                fig.add_trace(
                    go.Scatter(
                        x=pred["year"],
                        y=pred["fertility_rate"],
                        mode="lines",
                        name=f"{country_name(iso)} projected",
                        line=dict(color=line_color(iso, idx), width=2, dash="dash"),
                        hovertemplate="%{x}<br>%{y:.2f} children per woman<extra></extra>",
                    ),
                )

        fig.add_hline(
            y=2.1,
            line_width=2,
            line_dash="dash",
            line_color="#94a3b8",
            annotation_text="Replacement 2.1",
            annotation_position="top left",
        )

        if "KOR" in selected_isos:
            korea = visible_time_series(df_countries[df_countries["iso_alpha"].eq("KOR")])
            korea = korea[korea["fertility_rate"].notna()]
            if not korea.empty:
                low = korea.loc[korea["fertility_rate"].idxmin()]
                fig.add_annotation(
                    x=int(low["year"]),
                    y=float(low["fertility_rate"]),
                    text=f"Korea {low['fertility_rate']:.2f}",
                    showarrow=True,
                    arrowhead=2,
                    ax=-18,
                    ay=-34,
                    font=dict(size=11, color="#f8fafc"),
                )

        ct = _chart_theme()
        fig.update_layout(
            template=ct["template"],
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=34, r=24, t=76, b=58),
            height=430,
            hovermode="x unified",
            hoverlabel=dict(bgcolor=ct["hover_bg"], bordercolor=ct["hover_border"], font=dict(color=ct["hover_font"], size=12)),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor=ct["legend_bg"],
                bordercolor=ct["gridcolor"],
                borderwidth=1,
                font=dict(color=ct["legend_font"], size=12),
            ),
        )
        fig.update_xaxes(title_text="Year", title_standoff=12, gridcolor=ct["gridcolor"])
        fig.update_yaxes(title_text="Children per woman", gridcolor=ct["gridcolor"])
        return fig

    @render_widget
    def fertility_population_structure():
        if open_story_id() != "fertility":
            return go.Figure()
        iso = selected_story_country("fertility_structure_country", "KOR")
        compare_year = chart_year()
        baseline = age_structure(iso, 1950)
        current = age_structure(iso, compare_year)
        fig = go.Figure()
        fig.add_bar(
            y=baseline["age_group"],
            x=baseline["share"],
            orientation="h",
            name="1950",
            marker_color="rgba(148, 163, 184, 0.58)",
            hovertemplate="1950<br>%{y}: %{x:.1f}%<extra></extra>",
        )
        fig.add_bar(
            y=current["age_group"],
            x=current["share"],
            orientation="h",
            name=str(int(current["year"].iloc[0])) if not current.empty else str(compare_year),
            marker_color=COUNTRY_META.get(iso, {}).get("color", "#ef4444"),
            hovertemplate="%{fullData.name}<br>%{y}: %{x:.1f}%<extra></extra>",
        )
        fig = apply_story_layout(fig, f"{country_name(iso)} population share", 360)
        fig.update_layout(barmode="group", margin=dict(l=34, r=24, t=76, b=58))
        fig.update_xaxes(title_text="Share of population (%)")
        fig.update_yaxes(autorange="reversed")
        return fig

    @render_widget
    def fertility_socioeconomic_scatter():
        if open_story_id() != "fertility":
            return go.Figure()
        metric = selected_metric()
        frame = fertility_scatter_frame()
        if metric == "population_density":
            frame = frame[frame[metric].gt(0) & frame[metric].le(50_000)].copy()
        fig = go.Figure()
        selected_isos = selected_story_isos()
        selected_set = set(selected_isos)
        non_story = frame[~frame["iso_alpha"].isin(selected_set)]
        story = frame[frame["iso_alpha"].isin(selected_set)]

        fig.add_scatter(
            x=non_story[metric],
            y=non_story["fertility_rate"],
            mode="markers",
            name="Other countries",
            marker=dict(
                color="rgba(148, 163, 184, 0.38)",
                size=np.clip(np.sqrt(non_story["pop"].fillna(0)) / 900, 5, 18),
                line=dict(width=0),
            ),
            text=non_story["country"],
            hovertemplate="%{text}<br>%{x:.2f}<br>%{y:.2f} children per woman<extra></extra>",
        )

        for idx, iso in enumerate(selected_isos):
            country_df = story[story["iso_alpha"].eq(iso)]
            if country_df.empty:
                continue
            fig.add_scatter(
                x=country_df[metric],
                y=country_df["fertility_rate"],
                mode="markers+text",
                name=country_name(iso),
                text=[country_name(iso)],
                textposition="top center",
                marker=dict(
                    color=line_color(iso, idx),
                    size=13,
                    line=dict(color="#f8fafc", width=1.4),
                ),
                hovertemplate="%{text}<br>%{x:.2f}<br>%{y:.2f} children per woman<extra></extra>",
            )

        trend = frame[[metric, "fertility_rate"]].dropna()
        trend = trend[trend[metric].gt(0)] if metric == "population_density" else trend
        if len(trend) > 3:
            x_values = trend[metric].to_numpy(dtype=float)
            y_values = trend["fertility_rate"].to_numpy(dtype=float)
            fit_x = np.log10(x_values) if metric == "population_density" else x_values
            slope, intercept = np.polyfit(fit_x, y_values, 1)
            if metric == "population_density":
                x_line = np.geomspace(max(x_values.min(), 0.1), x_values.max(), 120)
                y_line = slope * np.log10(x_line) + intercept
            else:
                x_line = np.linspace(x_values.min(), x_values.max(), 120)
                y_line = slope * x_line + intercept
            fig.add_scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                name="Global trend",
                line=dict(color="#f8fafc", width=2, dash="dash"),
                hoverinfo="skip",
            )

        fig = apply_story_layout(fig, "Fertility rate", 430)
        fig.update_layout(hovermode="closest")
        fig.update_xaxes(title_text=SOCIOECONOMIC_METRICS[metric])
        if metric == "population_density":
            fig.update_xaxes(
                type="log",
                range=[0, np.log10(50_000)],
                tickvals=[1, 10, 100, 1_000, 10_000],
                ticktext=["1", "10", "100", "1k", "10k"],
            )
        return fig

    @render_widget
    def fertility_kmeans_clusters():
        if open_story_id() != "fertility":
            return go.Figure()
        frame = kmeans_cluster_frame()
        fig = go.Figure()
        if frame.empty:
            return fig

        selected_set = set(selected_story_isos())
        cluster_palette = ["#818cf8", "#22d3ee", "#ef4444", "#22c55e", "#f59e0b", "#e879f9", "#14b8a6", "#94a3b8"]
        for idx, cluster in enumerate(sorted(frame["cluster"].unique())):
            cluster_df = frame[frame["cluster"].eq(cluster)]
            fig.add_scatter(
                x=cluster_df["pca_x"],
                y=cluster_df["pca_y"],
                mode="markers",
                name=f"Cluster {cluster}",
                marker=dict(
                    color=cluster_palette[idx % len(cluster_palette)],
                    size=np.where(cluster_df["iso_alpha"].isin(selected_set), 14, 7),
                    opacity=np.where(cluster_df["iso_alpha"].isin(selected_set), 0.95, 0.55),
                    line=dict(color="#f8fafc", width=np.where(cluster_df["iso_alpha"].isin(selected_set), 1.4, 0)),
                ),
                text=cluster_df["country"],
                customdata=cluster_df[["fertility_rate", "elder_share", "population_growth_rate"]],
                hovertemplate=(
                    "%{text}<br>TFR %{customdata[0]:.2f}"
                    "<br>65+ %{customdata[1]:.1f}%"
                    "<br>Growth %{customdata[2]:+.2f}%<extra></extra>"
                ),
            )

        label_df = frame[frame["iso_alpha"].isin(selected_set)]
        fig.add_scatter(
            x=label_df["pca_x"],
            y=label_df["pca_y"],
            mode="text",
            text=[country_name(iso) for iso in label_df["iso_alpha"]],
            textposition="top center",
            textfont=dict(color=_chart_theme()["text_primary"], size=11),
            showlegend=False,
            hoverinfo="skip",
        )
        fig = apply_story_layout(fig, "PCA 2", 430)
        fig.update_layout(hovermode="closest")
        fig.update_xaxes(title_text="PCA 1")
        return fig

    @render_widget
    def fertility_lowest_ranking():
        if open_story_id() != "fertility":
            return go.Figure()
        year = input.timeline_year()
        year_df = df_countries[
            df_countries["year"].eq(year)
            & df_countries["fertility_rate"].notna()
            & df_countries["pop"].fillna(0).gt(500_000)
        ].copy()
        year_df = year_df.nsmallest(12, "fertility_rate").sort_values("fertility_rate", ascending=True)
        selected = set(selected_story_isos())

        fig = go.Figure()
        fig.add_bar(
            y=year_df["country"],
            x=year_df["fertility_rate"],
            orientation="h",
            marker_color=[
                COUNTRY_META.get(iso, {}).get("color", "#64748b") if iso in selected else "#64748b"
                for iso in year_df["iso_alpha"]
            ],
            text=[f"{value:.2f}" for value in year_df["fertility_rate"]],
            textposition="auto",
            hovertemplate="%{y}<br>%{x:.2f} children per woman<extra></extra>",
        )
        fig.add_vline(x=2.1, line_width=2, line_dash="dash", line_color="#94a3b8")
        fig.add_annotation(
            x=2.1,
            y=0.98,
            yref="paper",
            text="Replacement 2.1",
            showarrow=False,
            font=dict(color="#cbd5e1", size=11),
        )
        fig = apply_story_layout(fig, "Children per woman", 430)
        fig.update_layout(showlegend=False, margin=dict(l=30, r=24, t=24, b=54))
        fig.update_yaxes(automargin=True)
        return fig


    @render_widget
    def extinction_watch():
        """Show countries projected to have critically low fertility by 2030."""
        if open_story_id() != "fertility":
            return go.Figure()
        if not has_predictions() or not input.show_projections():
            return go.Figure()

        year_now = 2023
        year_future = PROJECTION_END_YEAR

        # Get 2023 and projected data
        df_2023 = df_countries[
            df_countries["year"].eq(year_now)
            & df_countries["fertility_rate"].notna()
            & df_countries["pop"].fillna(0).gt(500_000)
        ].copy()
        df_future = df_countries[
            df_countries["year"].eq(year_future)
            & df_countries["fertility_rate"].notna()
            & df_countries["pop"].fillna(0).gt(500_000)
        ].copy()

        if df_future.empty:
            return go.Figure()

        # Top 12 lowest predicted fertility at the projection horizon
        top12 = df_future.nsmallest(12, "fertility_rate").sort_values("fertility_rate", ascending=True)
        selected = set(selected_story_isos())

        fig = go.Figure()

        # Projected bar
        fig.add_bar(
            y=top12["country"],
            x=top12["fertility_rate"],
            orientation="h",
            name=f"{year_future} projected",
            marker_color=[
                COUNTRY_META.get(iso, {}).get("color", "#ef4444") if iso in selected else "#ef4444"
                for iso in top12["iso_alpha"]
            ],
            text=[f"{v:.2f}" for v in top12["fertility_rate"]],
            textposition="auto",
            hovertemplate=f"%{{y}}<br>{year_future}: %{{x:.2f}}<extra></extra>",
        )

        # 2023 marker overlay
        iso_2023_map = {}
        for _, r in df_2023.iterrows():
            iso_2023_map[r["iso_alpha"]] = r["fertility_rate"]

        markers_2023 = [iso_2023_map.get(iso, None) for iso in top12["iso_alpha"]]
        fig.add_scatter(
            x=markers_2023,
            y=top12["country"],
            mode="markers",
            name="2023 actual",
            marker=dict(color="#f8fafc", size=10, symbol="diamond", line=dict(color="#0f172a", width=1)),
            hovertemplate="%{y}<br>2023: %{x:.2f}<extra></extra>",
        )

        fig.add_vline(x=2.1, line_width=2, line_dash="dash", line_color="#94a3b8")
        fig.add_annotation(
            x=2.1, y=0.98, yref="paper",
            text="Replacement 2.1",
            showarrow=False,
            font=dict(color="#cbd5e1", size=11),
        )

        fig = apply_story_layout(fig, "Children per woman", 430)
        fig.update_layout(showlegend=True, margin=dict(l=34, r=24, t=76, b=58))
        fig.update_yaxes(automargin=True)
        return fig

app = App(app_ui, server)
