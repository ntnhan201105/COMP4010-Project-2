from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget


# --- Story Configuration ---
# Story 1: Refugee Crisis & Geopolitical Shockwaves
MIGRATION_OUTFLOW = ["SYR"]                         # Out-migration origin
MIGRATION_NEIGHBORS = ["TUR", "LBN", "JOR"]         # Neighboring hosts
MIGRATION_LONG = ["DEU"]                            # Long-distance host
MIGRATION_CONTRAST = ["POL", "UKR"]                 # Historical contrast
MIGRATION_ISOS = MIGRATION_OUTFLOW + MIGRATION_NEIGHBORS + MIGRATION_LONG + MIGRATION_CONTRAST

# Story 2: Ultra-Low Fertility Cliff
FERTILITY_COLLAPSE = ["KOR", "TWN", "JPN"]          # Collapse group
FERTILITY_SCALE = ["CHN"]                           # Scale shift
FERTILITY_HIGH = ["NER", "TCD", "MLI"]              # High-fertility contrast
FERTILITY_ISOS = FERTILITY_COLLAPSE + FERTILITY_SCALE + FERTILITY_HIGH

COUNTRY_META = {
    # ── Migration story ──
    "SYR": {"name": "Syria", "color": "#ef4444", "role": "Out-migration origin"},
    "TUR": {"name": "Turkey", "color": "#f97316", "role": "Neighboring host"},
    "LBN": {"name": "Lebanon", "color": "#fb923c", "role": "Neighboring host"},
    "JOR": {"name": "Jordan", "color": "#fbbf24", "role": "Neighboring host"},
    "DEU": {"name": "Germany", "color": "#22d3ee", "role": "Long-distance host"},
    "POL": {"name": "Poland", "color": "#a78bfa", "role": "Historical contrast"},
    "UKR": {"name": "Ukraine", "color": "#818cf8", "role": "Historical contrast"},
    # ── Fertility story ──
    "KOR": {"name": "South Korea", "color": "#ef4444", "role": "Demographic collapse"},
    "TWN": {"name": "Taiwan", "color": "#fb7185", "role": "Demographic collapse"},
    "JPN": {"name": "Japan", "color": "#f59e0b", "role": "Demographic collapse"},
    "CHN": {"name": "China", "color": "#f97316", "role": "Scale shift"},
    "NER": {"name": "Niger", "color": "#10d97a", "role": "High fertility"},
    "TCD": {"name": "Chad", "color": "#22d3ee", "role": "High fertility"},
    "MLI": {"name": "Mali", "color": "#34d399", "role": "High fertility"},
}

STORY_CONFIGS = {
    "migration": {
        "label": "Refugee Crisis",
        "indicator": "net_migration_rate",
        "eyebrow": "Refugee Crisis & Geopolitical Shockwaves",
        "title": "Capturing the Ripple Effects of Displacement",
        "copy": (
            "Conflict-driven migration creates asymmetric burdens: small neighboring nations "
            "absorb displacement waves, while long-distance hosts receive selective inflows. "
            "Brush the timeline to explore how shocks propagate across borders."
        ),
        "isos": MIGRATION_ISOS,
        "origins": MIGRATION_OUTFLOW,
        "hosts": MIGRATION_NEIGHBORS + MIGRATION_LONG,
        "target": {"longitude": 28, "latitude": 38, "zoom": 1.18},
    },
    "fertility": {
        "label": "Fertility Cliff",
        "indicator": "fertility_rate",
        "eyebrow": "The Ultra-Low Fertility Cliff",
        "title": "Tracking East Asia's Demographic Winter",
        "copy": (
            "South Korea, Taiwan, and Japan have fallen far below the 2.1 replacement level, "
            "while Niger, Chad, and Mali remain at the opposite extreme. China sits at a pivotal "
            "scale — the world's largest population now in decline."
        ),
        "isos": FERTILITY_ISOS,
        "origins": [],
        "hosts": [],
        "target": {"longitude": 128, "latitude": 30, "zoom": 1.42},
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
df_countries = df_full[df_full["is_country"]].copy()
df_world = df_full[df_full["iso_alpha"].eq("WORLD")].copy()
min_year = int(df_full["year"].min())
max_year = int(df_full["year"].max())


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


def story_from_indicator(indicator: str | None) -> str | None:
    for story_id, config in STORY_CONFIGS.items():
        if indicator == config["indicator"]:
            return story_id
    return None


def story_choices(story_id: str | None) -> dict[str, str]:
    if story_id not in STORY_CONFIGS:
        return {}
    return {iso: country_name(iso) for iso in STORY_CONFIGS[story_id]["isos"]}


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
        ui.h2("Scars on the Map", class_="mb-4"),
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
            "Show ML projections to 2040",
            value=False,
        ),
        ui.input_slider(
            "timeline_year",
            "Select Year",
            min=min_year,
            max=max_year,
            value=max_year,
            step=1,
            animate=ui.AnimationOptions(loop=False, interval=260),
            sep="",
        ),
        ui.input_select(
            "indicator",
            "Globe Lens",
            choices={
                "net_migration_rate": "★ Migration Rate",
                "fertility_rate": "★ Birth Rate (Fertility)",
                "life_expectancy": "Life Expectancy",
                "child_mortality": "Child Mortality",
                "death_rate": "Death Rate",
            },
            selected="net_migration_rate",
        ),
        ui.output_ui("open_story_control"),
        ui.output_ui("story_country_filter"),
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
            ui.div(
                ui.h3("Scars on the Map", class_="globe-callout-title"),
                ui.p(
                    "Use the migration and fertility lenses to turn the globe into a story view.",
                    class_="globe-callout-copy",
                ),
                class_="globe-story-callout",
            ),
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
                        "Capturing the Ripple Effects of Displacement",
                        "Conflict-driven migration creates asymmetric burdens: small neighboring "
                        "nations absorb displacement waves, while long-distance hosts receive "
                        "selective inflows. Brush the timeline to explore how shocks propagate "
                        "across borders."
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch corridor-origin"), " Out-migration origin"),
                        ui.span(ui.span(class_="corridor-swatch corridor-host"), " Host / receiving"),
                        ui.span(ui.span(class_="corridor-swatch", style="background:#a78bfa;color:#a78bfa;"), " Contrast"),
                        class_="corridor-legend",
                    ),
                    ui.div(
                        ui.input_select(
                            "migration_focus_country",
                            "Select country for forecast & age structure",
                            choices={iso: country_name(iso) for iso in MIGRATION_ISOS},
                            selected=MIGRATION_OUTFLOW[0],
                        ),
                        class_="story-sidebar-block",
                    ),
                    # Fig 1: Multi-line net migration with brushing
                    ui.card(
                        ui.card_header("Net Migration Rate 1990–2023 (brush to filter)"),
                        output_widget("migration_multiline"),
                    ),
                    # Fig 2: Migration burden bar chart
                    ui.card(
                        ui.card_header("Migration Burden by Country"),
                        output_widget("migration_burden_bars"),
                    ),
                    # Fig 3: Population structure
                    ui.card(
                        ui.card_header("Population Age Structure"),
                        output_widget("migration_age_structure"),
                    ),
                    # Fig 4: ARIMA forecast
                    ui.card(
                        ui.card_header("ARIMA Forecast with Confidence Ribbon"),
                        output_widget("migration_arima_forecast"),
                    ),
                    class_="story-dashboard-body",
                ),
            ),
            ui.panel_conditional(
                "input.indicator == 'fertility_rate'",
                ui.div(
                    story_intro(
                        "Tracking East Asia's Demographic Winter",
                        "South Korea, Taiwan, and Japan have fallen far below the 2.1 replacement "
                        "level, while Niger, Chad, and Mali remain at the opposite extreme. "
                        "China sits at a pivotal scale — the world's largest population now in decline."
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch fertility-low"), " Ultra-low fertility"),
                        ui.span(ui.span(class_="corridor-swatch fertility-replacement"), " Replacement 2.1"),
                        ui.span(ui.span(class_="corridor-swatch", style="background:#10d97a;color:#10d97a;"), " High fertility"),
                        class_="corridor-legend",
                    ),
                    ui.div(
                        ui.input_select(
                            "fertility_focus_country",
                            "Select country for age structure comparison",
                            choices={iso: country_name(iso) for iso in FERTILITY_ISOS},
                            selected=FERTILITY_COLLAPSE[0],
                        ),
                        class_="story-sidebar-block",
                    ),
                    # Fig 1: Dual-axis multi-line TFR
                    ui.card(
                        ui.card_header("Fertility Rate vs Replacement Level"),
                        output_widget("fertility_multiline"),
                    ),
                    # Fig 2: Population age structure comparison
                    ui.card(
                        ui.card_header("Population Age Structure: Pyramid vs Inverted Block"),
                        output_widget("fertility_age_structure"),
                    ),
                    # Fig 3: Socioeconomic scatter
                    ui.card(
                        ui.card_header("Urban Density vs Fertility (Global Context)"),
                        output_widget("fertility_scatter"),
                    ),
                    # Fig 4: K-Means clustering
                    ui.card(
                        ui.card_header("K-Means Clustering: Demographic Winter Detection"),
                        ui.input_slider(
                            "kmeans_k",
                            "Number of Clusters (K)",
                            min=2, max=8, value=3, step=1,
                        ),
                        output_widget("fertility_kmeans"),
                    ),
                    class_="story-dashboard-body",
                ),
            ),
            class_="story-dashboard-panel",
        ),
        id="story-stage",
        class_="story-stage",
    ),
    title="Scars on the Map",
)


def server(input, output, session):
    selected_country = reactive.Value(None)
    story_locked_indicator = reactive.Value(None)  # indicator when story was explicitly opened
    theme = reactive.Value("dark")
    # Cross-filtering state for story charts
    story_brushed_years = reactive.Value(None)       # (min_year, max_year) from brush
    story_selected_country = reactive.Value(None)     # iso from clicking story charts
    story_migration_base_year = reactive.Value(1990)  # start year for migration charts

    @reactive.Calc
    def story_panel_open() -> bool:
        """Panel is open only when indicator hasn't changed since opening.
        Depends on input.indicator() so mismatch is caught at Calc-time,
        BEFORE any story charts get a chance to render."""
        locked = story_locked_indicator.get()
        if locked is None:
            return False
        return locked == input.indicator()

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
        return 2023

    @reactive.Effect
    @reactive.event(input.show_projections)
    def _sync_slider_range():
        ui.update_slider("timeline_year", max=effective_max_year())

    # ── Story Cross-Filtering Reactives ──────────────────────────────
    @reactive.Calc
    def story_effective_year() -> int:
        """Year used for snapshot charts: brushed midpoint or slider year."""
        brush = story_brushed_years.get()
        if brush is not None:
            return int(round((brush[0] + brush[1]) / 2))
        return input.timeline_year()

    @reactive.Calc
    def story_migration_data() -> pd.DataFrame:
        """Filtered data for migration story countries, 1990 onward."""
        return df_countries[
            df_countries["iso_alpha"].isin(MIGRATION_ISOS)
            & df_countries["year"].ge(story_migration_base_year.get())
        ].copy()

    @reactive.Calc
    def story_fertility_data() -> pd.DataFrame:
        """Filtered data for fertility story countries."""
        return df_countries[
            df_countries["iso_alpha"].isin(FERTILITY_ISOS)
        ].copy()

    @reactive.Calc
    def story_global_2023() -> pd.DataFrame:
        """All countries, latest historical year, for scatter/clustering."""
        return df_countries[
            df_countries["year"].eq(2023)
            & df_countries["fertility_rate"].notna()
            & df_countries["population_density"].notna()
            & df_countries["pop"].fillna(0).gt(500_000)
        ].copy()

    @reactive.Calc
    def story_kmeans_result() -> dict:
        """K-Means clustering on global 2023 data. Re-runs when K changes."""
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        k = input.kmeans_k() if hasattr(input, 'kmeans_k') else 3
        try:
            k = int(k)
        except Exception:
            k = 3
        k = max(2, min(8, k))

        data = story_global_2023()
        feats = ["fertility_rate", "lifeExp", "population_growth_rate", "child_mortality"]
        X = data[feats].dropna()
        if len(X) < k:
            return {"labels": [], "centers": None, "pca": None, "isos": [], "k": k}

        X_scaled = StandardScaler().fit_transform(X)
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled)

        from sklearn.decomposition import PCA
        pca = PCA(n_components=2).fit_transform(X_scaled)

        return {
            "labels": km.labels_.tolist(),
            "centers": km.cluster_centers_,
            "pca": pca,
            "isos": data.loc[X.index, "iso_alpha"].tolist(),
            "k": k,
        }

    @reactive.Calc
    def _cached_arima_forecast() -> dict:
        """Cached ARIMA forecast — only re-fits when country or projection changes.
        Returns None if story is not open, empty dict on failure."""
        if open_story_id() != "migration":
            return {}
        sel_iso = input.migration_focus_country() or MIGRATION_OUTFLOW[0]
        country_df = df_countries[
            df_countries["iso_alpha"].eq(sel_iso)
        ].sort_values("year")
        if country_df.empty:
            return {}

        hist = country_df[country_df["year"].between(1990, 2023)]
        series = hist["net_migration_rate"].dropna()
        if len(series) < 10:
            return {}

        result = {"iso": sel_iso, "historical_years": hist["year"].tolist(),
                  "historical_values": hist["net_migration_rate"].tolist(),
                  "pred_years": list(range(2024, 2041)), "success": False}

        # Try ARIMA first
        try:
            from statsmodels.tsa.arima.model import ARIMA
            model = ARIMA(series.values, order=(2, 1, 2))
            fit = model.fit()
            forecast = fit.get_forecast(steps=17)
            result["mean"] = forecast.predicted_mean.tolist()
            ci = forecast.conf_int(alpha=0.05)
            result["ci_lower"] = ci[:, 0].tolist()
            result["ci_upper"] = ci[:, 1].tolist()
            result["success"] = True
            result["method"] = "ARIMA(2,1,2)"
            return result
        except Exception:
            pass

        # Fallback: linear regression with ±2σ band
        try:
            X = np.arange(len(series)).reshape(-1, 1).astype(float)
            y = series.values.astype(float)
            from sklearn.linear_model import LinearRegression
            lr = LinearRegression().fit(X, y)
            residuals = y - lr.predict(X)
            std = float(np.std(residuals))
            pred_idx = np.arange(len(series), len(series) + 17).reshape(-1, 1).astype(float)
            pred_mean = lr.predict(pred_idx)
            result["mean"] = pred_mean.tolist()
            result["ci_lower"] = (pred_mean - 2 * std).tolist()
            result["ci_upper"] = (pred_mean + 2 * std).tolist()
            result["success"] = True
            result["method"] = "Linear trend ±2σ"
            return result
        except Exception:
            return result

    @reactive.Calc
    def _cached_scatter_data() -> dict:
        """Pre-computed scatter data for fertility Fig 3. Cached globally."""
        data = story_global_2023()
        if data.empty:
            return {"x": [], "y": [], "countries": [], "isos": [], "trend_x": [], "trend_y": []}

        valid = data.dropna(subset=["population_density", "fertility_rate"])
        result = {
            "x": valid["population_density"].tolist(),
            "y": valid["fertility_rate"].tolist(),
            "countries": valid["country"].tolist(),
            "isos": valid["iso_alpha"].tolist(),
        }

        # Polynomial trend line
        try:
            x = valid["population_density"].values
            y = valid["fertility_rate"].values
            coeffs = np.polyfit(x, y, 2)
            x_trend = np.linspace(x.min(), x.max(), 100)
            y_trend = np.polyval(coeffs, x_trend)
            result["trend_x"] = x_trend.tolist()
            result["trend_y"] = y_trend.tolist()
        except Exception:
            result["trend_x"] = []
            result["trend_y"] = []

        return result

    @reactive.Calc
    def active_story() -> str | None:
        return story_from_indicator(input.indicator())

    @reactive.Calc
    def open_story_id() -> str | None:
        """Returns story_id only when panel is open. story_panel_open Calc
        already catches indicator changes at Calc-time, so charts never render
        for a story that should be closed."""
        if not story_panel_open():
            return None
        story_id = active_story()
        if story_id in STORY_CONFIGS:
            return story_id
        return None

    @reactive.Calc
    def selected_story_isos() -> list[str]:
        story_id = open_story_id()
        if story_id not in STORY_CONFIGS:
            return []

        allowed = STORY_CONFIGS[story_id]["isos"]
        selected = input.story_countries()
        if selected is None:
            return allowed
        if isinstance(selected, str):
            selected = [selected]
        selected = [iso for iso in selected if iso in allowed]
        return selected or allowed

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

    @render.ui
    def story_country_filter():
        story_id = active_story()
        if story_id not in STORY_CONFIGS:
            return None
        if not story_panel_open():
            return None
        return ui.div(
            ui.input_selectize(
                "story_countries",
                "Filter countries in story charts",
                choices=story_choices(story_id),
                selected=STORY_CONFIGS[story_id]["isos"],
                multiple=True,
            ),
            class_="story-sidebar-block",
        )

    @reactive.Effect
    @reactive.event(input.indicator)
    def handle_indicator_change():
        """Clear lock → story_panel_open Calc immediately returns False at Calc-time."""
        story_locked_indicator.set(None)

    @reactive.Effect
    @reactive.event(input.open_story)
    def handle_open_story():
        if active_story() in STORY_CONFIGS:
            story_locked_indicator.set(input.indicator())  # lock to current indicator

    @reactive.Effect
    @reactive.event(input.close_story_panel)
    def handle_close_story_panel():
        story_locked_indicator.set(None)

    # ── Cross-Filtering: Country Selectors ──────────────────────────
    @reactive.Effect
    @reactive.event(input.migration_focus_country)
    def _sync_migration_focus():
        iso = input.migration_focus_country()
        if iso:
            story_selected_country.set(iso)

    @reactive.Effect
    @reactive.event(input.fertility_focus_country)
    def _sync_fertility_focus():
        iso = input.fertility_focus_country()
        if iso:
            story_selected_country.set(iso)

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
            hist = country_df
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

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Convert hex color like '#ef4444' to RGB tuple."""
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

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
            hist = country_df.sort_values("year")
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
            margin=dict(l=30, r=24, t=24, b=94),
            height=height,
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor=ct["hover_bg"],
                bordercolor=ct["hover_border"],
                font=dict(color=ct["hover_font"], size=12),
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
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
        fig.update_yaxes(title_text=y_title, gridcolor=ct["gridcolor"])
        return fig

    # ═══════════════════════════════════════════════════════════════════
    # Story 1: Refugee Crisis & Geopolitical Shockwaves (Migration)
    # ═══════════════════════════════════════════════════════════════════

    @render_widget
    def migration_multiline():
        """Fig 1: Multi-line net migration 1990–2023 with ARIMA forecast overlay."""
        if open_story_id() != "migration":
            return go.Figure()
        selected_isos = selected_story_isos()
        fig = go.Figure()
        add_conflict_shading(fig, [iso for iso in selected_isos if iso in MIGRATION_OUTFLOW])

        for iso in selected_isos:
            country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
            if country_df.empty:
                continue
            hist = country_df[country_df["year"].le(2023)]
            is_outflow = iso in MIGRATION_OUTFLOW
            add_country_lines(
                fig, hist, "net_migration_rate",
                name=country_name(iso),
                color=COUNTRY_META[iso]["color"],
                width=3.2 if is_outflow else 2.2,
                dash_solid="solid" if is_outflow else "dot",
                show_pred=False,
            )

        fig.add_hline(y=0, line_width=1.5, line_dash="dot", line_color="#94a3b8")
        fig = apply_story_layout(fig, "Migrants per 1,000 people", 460)
        fig.update_layout(
            dragmode="select",
            selectdirection="h",
            xaxis=dict(range=[1990, 2043]),
        )
        return fig

    # ── FigureWidgets for frequently-updated charts ──────────────────
    _mig_burden_fig = go.FigureWidget()
    _mig_burden_fig.add_bar(y=[], x=[], orientation="h", marker_color=[], text=[],
                             hovertemplate="%{y}<br>%{x:+.2f} per 1,000<extra></extra>")
    _mig_burden_fig.add_vline(x=0, line_width=1.5, line_dash="dot", line_color="#94a3b8")
    _mig_burden_fig.update_layout(showlegend=False, margin=dict(l=30, r=24, t=24, b=54),
                                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=350)
    _mig_burden_fig.update_yaxes(automargin=True)
    _mig_burden_fig.update_xaxes(title_text="Net migration rate")

    _mig_age_fig = go.FigureWidget()
    _mig_age_fig.add_bar(y=[], x=[], orientation="h", marker_color=[], text=[],
                          hovertemplate="%{y}: %{x:.1f}%<extra></extra>")
    _mig_age_fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                 height=380, showlegend=False, margin=dict(l=30, r=24, t=40, b=54))
    _mig_age_fig.update_xaxes(title_text="% of population")
    _mig_age_fig.update_yaxes()

    @render_widget
    def migration_burden_bars():
        """Fig 2: Migration burden — updated via reactive effect."""
        return _mig_burden_fig

    @reactive.Effect
    def _update_migration_burden_bars():
        """Update burden bars data when year or countries change.
        Clears data immediately when story closes."""
        if open_story_id() != "migration":
            with _mig_burden_fig.batch_update():
                _mig_burden_fig.data[0].y = []
                _mig_burden_fig.data[0].x = []
                _mig_burden_fig.data[0].text = []
            return
        year = story_effective_year()
        selected_isos = selected_story_isos()

        rows = []
        for iso in selected_isos:
            country_df = df_countries[
                df_countries["iso_alpha"].eq(iso)
                & df_countries["year"].eq(year)
            ]
            if country_df.empty:
                continue
            rows.append({
                "country": country_name(iso),
                "iso": iso,
                "value": float(country_df["net_migration_rate"].iloc[0]),
            })
        rows.sort(key=lambda r: r["value"])

        ct = _chart_theme()
        year_labels = [f"{r['value']:+.1f}" for r in rows]
        with _mig_burden_fig.batch_update():
            _mig_burden_fig.data[0].y = [r["country"] for r in rows]
            _mig_burden_fig.data[0].x = [r["value"] for r in rows]
            _mig_burden_fig.data[0].marker.color = [COUNTRY_META[r["iso"]]["color"] for r in rows]
            _mig_burden_fig.data[0].text = year_labels
            _mig_burden_fig.layout.template = ct["template"]
            _mig_burden_fig.layout.xaxis.title.text = f"Net migration rate ({year})"
            _mig_burden_fig.layout.xaxis.gridcolor = ct["gridcolor"]
            _mig_burden_fig.layout.yaxis.gridcolor = ct["gridcolor"]

    @render_widget
    def migration_age_structure():
        """Fig 3: Age structure — updated via reactive effect."""
        return _mig_age_fig

    @reactive.Effect
    def _update_migration_age_structure():
        """Update age structure data when year or country changes.
        Clears data immediately when story closes."""
        if open_story_id() != "migration":
            with _mig_age_fig.batch_update():
                _mig_age_fig.data[0].y = []
                _mig_age_fig.data[0].x = []
                _mig_age_fig.data[0].text = []
                _mig_age_fig.layout.title = ""
            return
        year = story_effective_year()
        sel_iso = input.migration_focus_country() or MIGRATION_OUTFLOW[0]
        country_df = df_countries[
            df_countries["iso_alpha"].eq(sel_iso)
            & df_countries["year"].eq(year)
        ]
        if country_df.empty:
            return

        row = country_df.iloc[0]
        age_groups = ["0-4", "5-14", "15-24", "25-64", "65+"]
        age_cols = ["age_0_4", "age_5_14", "age_15_24", "age_25_64", "age_65_plus"]
        values = [float(row[c]) for c in age_cols]
        total = sum(values)
        percentages = [v / total * 100 for v in values]

        ct = _chart_theme()
        with _mig_age_fig.batch_update():
            _mig_age_fig.data[0].y = age_groups
            _mig_age_fig.data[0].x = percentages
            _mig_age_fig.data[0].marker.color = [
                "#818cf8" if g == "25-64" else "#ef4444" if g == "15-24" else "#94a3b8"
                for g in age_groups
            ]
            _mig_age_fig.data[0].text = [f"{p:.1f}%" for p in percentages]
            _mig_age_fig.layout.template = ct["template"]
            _mig_age_fig.layout.title = f"{country_name(sel_iso)} age structure ({year})"
            _mig_age_fig.layout.title.font.color = ct["text_primary"]
            _mig_age_fig.layout.xaxis.gridcolor = ct["gridcolor"]
            _mig_age_fig.layout.xaxis.title.font.color = ct["text_secondary"]
            _mig_age_fig.layout.yaxis.gridcolor = ct["gridcolor"]

    @render_widget
    def migration_arima_forecast():
        """Fig 4: ARIMA forecast with confidence ribbon — uses cached calc."""
        if open_story_id() != "migration":
            return go.Figure()

        fc = _cached_arima_forecast()
        if not fc or not fc.get("success"):
            return go.Figure()

        ct = _chart_theme()
        sel_iso = fc["iso"]
        fig = go.Figure()

        # Historical line
        fig.add_scatter(
            x=fc["historical_years"], y=fc["historical_values"],
            mode="lines+markers",
            name=f"{country_name(sel_iso)} historical",
            line=dict(color=COUNTRY_META[sel_iso]["color"], width=2.5),
            marker=dict(size=4),
        )

        # Forecast line
        fig.add_scatter(
            x=fc["pred_years"], y=fc["mean"],
            mode="lines",
            name=fc.get("method", "Forecast"),
            line=dict(color=COUNTRY_META[sel_iso]["color"], width=2, dash="dash"),
        )

        # Confidence ribbon
        if fc.get("ci_lower") and fc.get("ci_upper"):
            fig.add_scatter(
                x=fc["pred_years"] + fc["pred_years"][::-1],
                y=fc["ci_lower"] + fc["ci_upper"][::-1],
                fill="toself",
                fillcolor=f"rgba({','.join(str(int(c)) for c in _hex_to_rgb(COUNTRY_META[sel_iso]['color']))},0.15)",
                line=dict(width=0),
                name="95% CI",
                showlegend=True,
            )

        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#94a3b8")
        fig.add_vline(x=2023, line_width=1.5, line_dash="dash", line_color=ct["text_secondary"],
                       annotation_text="Forecast start", annotation_position="top")

        fig = apply_story_layout(fig, "Migrants per 1,000 people", 420)
        fig.update_layout(
            xaxis=dict(range=[1990, 2043]),
            legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0,
                        bgcolor=ct["legend_bg"], bordercolor=ct["gridcolor"],
                        borderwidth=1, font=dict(color=ct["legend_font"], size=11)),
        )
        return fig

    # ═══════════════════════════════════════════════════════════════════
    # Story 2: Ultra-Low Fertility Cliff
    # ═══════════════════════════════════════════════════════════════════

    @render_widget
    def fertility_multiline():
        """Fig 1: Dual-axis multi-line TFR with replacement level marker."""
        if open_story_id() != "fertility":
            return go.Figure()
        selected_isos = selected_story_isos()
        fig = go.Figure()

        # World average for context
        if not df_world.empty:
            world = df_world.sort_values("year")
            world_hist = world[world["year"].le(2023)]
            fig.add_scatter(
                x=world_hist["year"], y=world_hist["fertility_rate"],
                mode="lines",
                name="World average",
                line=dict(color="#94a3b8", width=3, dash="dot"),
            )

        for iso in selected_isos:
            country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
            if country_df.empty:
                continue
            add_country_lines(
                fig, country_df, "fertility_rate",
                name=country_name(iso),
                color=COUNTRY_META[iso]["color"],
                width=2.7,
            )

        # 2.1 replacement reference line
        fig.add_hline(
            y=2.1, line_width=2.5, line_dash="dash", line_color="#94a3b8",
            annotation_text="Replacement level 2.1", annotation_position="top left",
        )

        # Annotate Korea's minimum
        if "KOR" in selected_isos:
            korea = df_countries[df_countries["iso_alpha"].eq("KOR")]
            korea = korea[korea["fertility_rate"].notna()]
            if not korea.empty:
                low = korea.loc[korea["fertility_rate"].idxmin()]
                fig.add_annotation(
                    x=int(low["year"]), y=float(low["fertility_rate"]),
                    text=f"Korea {low['fertility_rate']:.2f}",
                    showarrow=True, arrowhead=2, ax=-18, ay=-34,
                    font=dict(size=11, color=_chart_theme()["text_primary"]),
                )

        fig = apply_story_layout(fig, "Children per woman", 460)
        fig.update_layout(xaxis=dict(range=[1960, 2043]))
        return fig

    @render_widget
    def fertility_age_structure():
        """Fig 2: Age structure comparison — pyramid (1990) vs inverted block (2023)."""
        if open_story_id() != "fertility":
            return go.Figure()
        sel_iso = input.fertility_focus_country() or FERTILITY_COLLAPSE[0]
        year_past = 1990
        year_now = 2023

        ct = _chart_theme()
        age_groups = ["0-4", "5-14", "15-24", "25-64", "65+"]
        age_cols = ["age_0_4", "age_5_14", "age_15_24", "age_25_64", "age_65_plus"]

        fig = go.Figure()
        for yr, dash_style, alpha in [(year_past, "dash", 0.55), (year_now, "solid", 1.0)]:
            cdf = df_countries[
                df_countries["iso_alpha"].eq(sel_iso)
                & df_countries["year"].eq(yr)
            ]
            if cdf.empty:
                continue
            row = cdf.iloc[0]
            values = [float(row[c]) for c in age_cols]
            total = sum(values)
            pcts = [v / total * 100 for v in values]

            fig.add_scatter(
                x=pcts, y=age_groups,
                mode="lines+markers",
                name=f"{yr}",
                line=dict(color=COUNTRY_META[sel_iso]["color"], width=2.5, dash=dash_style),
                marker=dict(size=8, symbol="circle"),
                opacity=alpha,
                hovertemplate="%{y}<br>%{x:.1f}%<extra></extra>",
            )

        fig.update_layout(
            template=ct["template"],
            title=f"{country_name(sel_iso)} age structure: {year_past} → {year_now}",
            title_font=dict(size=14, color=ct["text_primary"]),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=30, r=24, t=40, b=54),
            hovermode="y unified",
        )
        fig.update_xaxes(title_text="% of population", gridcolor=ct["gridcolor"],
                         title_font=dict(color=ct["text_secondary"]))
        fig.update_yaxes(gridcolor=ct["gridcolor"])
        return fig

    @render_widget
    def fertility_scatter():
        """Fig 3: Socioeconomic scatter — uses cached data for performance."""
        if open_story_id() != "fertility":
            return go.Figure()
        ct = _chart_theme()
        cached = _cached_scatter_data()
        if not cached.get("x"):
            return go.Figure()

        target_isos = set(selected_story_isos())

        fig = go.Figure()

        # All countries (gray background) — split target vs non-target
        non_tgt_x, non_tgt_y, non_tgt_text = [], [], []
        for i, iso in enumerate(cached["isos"]):
            if iso not in target_isos:
                non_tgt_x.append(cached["x"][i])
                non_tgt_y.append(cached["y"][i])
                non_tgt_text.append(cached["countries"][i])

        fig.add_scatter(
            x=non_tgt_x, y=non_tgt_y,
            mode="markers",
            name="All countries",
            marker=dict(color="#64748b", size=7, opacity=0.45),
            text=non_tgt_text,
            hovertemplate="%{text}<br>Density: %{x:.1f}/km²<br>TFR: %{y:.2f}<extra></extra>",
        )

        # Target countries highlighted
        for i, iso in enumerate(cached["isos"]):
            if iso in target_isos:
                fig.add_scatter(
                    x=[cached["x"][i]], y=[cached["y"][i]],
                    mode="markers+text",
                    name=country_name(iso),
                    marker=dict(color=COUNTRY_META.get(iso, {}).get("color", "#818cf8"),
                                size=14, symbol="diamond",
                                line=dict(color="white" if theme.get() == "dark" else "#0f172a", width=1.5)),
                    text=[country_name(iso)],
                    textposition="top center",
                    textfont=dict(size=11, color=ct["text_primary"]),
                    hovertemplate="%{text}<br>Density: %{x:.1f}/km²<br>TFR: %{y:.2f}<extra></extra>",
                )

        # Pre-computed trend line
        if cached.get("trend_x"):
            fig.add_scatter(
                x=cached["trend_x"], y=cached["trend_y"],
                mode="lines",
                name="Global trend (quadratic)",
                line=dict(color="#fbbf24", width=2.5, dash="dash"),
                hoverinfo="skip",
            )

        fig.add_hline(y=2.1, line_width=1.5, line_dash="dot", line_color="#94a3b8",
                       annotation_text="Replacement 2.1", annotation_position="top right")

        fig.update_layout(
            template=ct["template"],
            title="Population Density vs Fertility Rate (2023)",
            title_font=dict(size=14, color=ct["text_primary"]),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=420,
            margin=dict(l=30, r=24, t=40, b=74),
            legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
                        bgcolor=ct["legend_bg"], bordercolor=ct["gridcolor"],
                        borderwidth=1, font=dict(color=ct["legend_font"], size=10)),
        )
        fig.update_xaxes(title_text="Population density (people/km²)", type="log",
                         gridcolor=ct["gridcolor"], title_font=dict(color=ct["text_secondary"]))
        fig.update_yaxes(title_text="Fertility rate (children/woman)",
                         gridcolor=ct["gridcolor"], title_font=dict(color=ct["text_secondary"]))
        return fig

    @render_widget
    def fertility_kmeans():
        """Fig 4: K-Means clustering PCA projection with demographic winter detection."""
        if open_story_id() != "fertility":
            return go.Figure()
        ct = _chart_theme()
        km = story_kmeans_result()
        if km["pca"] is None or len(km["labels"]) == 0:
            return go.Figure()

        pca = np.array(km["pca"])
        labels = np.array(km["labels"])
        isos_list = km["isos"]
        k = km["k"]
        target_isos = set(selected_story_isos())

        # Cluster colors (distinct palette)
        cluster_colors = [
            "#818cf8", "#ef4444", "#10d97a", "#fbbf24", "#f97316",
            "#22d3ee", "#fb7185", "#a78bfa",
        ]

        fig = go.Figure()

        for cl in range(k):
            mask = labels == cl
            if not mask.any():
                continue
            cl_isos = set(isos_list[i] for i in range(len(isos_list)) if mask[i])
            targets_in_cl = cl_isos & target_isos

            # Non-target points in cluster
            non_tgt_mask = np.array([isos_list[i] not in target_isos for i in range(len(isos_list)) if mask[i]])
            cl_pca = pca[mask]
            non_tgt_pca = cl_pca[non_tgt_mask] if non_tgt_mask.any() else np.empty((0, 2))

            fig.add_scatter(
                x=non_tgt_pca[:, 0] if len(non_tgt_pca) > 0 else [],
                y=non_tgt_pca[:, 1] if len(non_tgt_pca) > 0 else [],
                mode="markers",
                name=f"Cluster {cl+1} ({len(cl_isos)} countries)",
                marker=dict(color=cluster_colors[cl % len(cluster_colors)], size=8, opacity=0.55),
                hoverinfo="skip",
            )

            # Target country points in cluster
            for i, iso in enumerate(isos_list):
                if mask[i] and iso in target_isos:
                    fig.add_scatter(
                        x=[pca[i, 0]], y=[pca[i, 1]],
                        mode="markers+text",
                        name=country_name(iso),
                        marker=dict(color=cluster_colors[cl % len(cluster_colors)], size=18,
                                    symbol="diamond",
                                    line=dict(color="white" if theme.get() == "dark" else "#0f172a", width=2)),
                        text=[country_name(iso)],
                        textposition="top center",
                        textfont=dict(size=11, color=ct["text_primary"]),
                        hovertemplate="%{text}<extra></extra>",
                        showlegend=False,
                    )

        fig.update_layout(
            template=ct["template"],
            title=f"K-Means Clustering (K={k}): Demographic Features PCA",
            title_font=dict(size=14, color=ct["text_primary"]),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=440,
            margin=dict(l=30, r=24, t=40, b=74),
            legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0,
                        bgcolor=ct["legend_bg"], bordercolor=ct["gridcolor"],
                        borderwidth=1, font=dict(color=ct["legend_font"], size=10)),
        )
        fig.update_xaxes(title_text="PC1", gridcolor=ct["gridcolor"],
                         title_font=dict(color=ct["text_secondary"]))
        fig.update_yaxes(title_text="PC2", gridcolor=ct["gridcolor"],
                         title_font=dict(color=ct["text_secondary"]))
        return fig

app = App(app_ui, server)
