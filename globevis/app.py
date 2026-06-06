from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget


# --- Story Configuration ---
MIGRATION_OUTFLOW = ["SYR", "YEM"]
MIGRATION_INFLOW = ["ARE", "QAT", "KWT", "OMN"]
FERTILITY_ISOS = ["KOR", "TWN", "HKG", "JPN"]

COUNTRY_META = {
    "SYR": {"name": "Syria", "color": "#ef4444", "role": "Outflow"},
    "YEM": {"name": "Yemen", "color": "#fb7185", "role": "Outflow"},
    "ARE": {"name": "United Arab Emirates", "color": "#22d3ee", "role": "Inflow"},
    "QAT": {"name": "Qatar", "color": "#38bdf8", "role": "Inflow"},
    "KWT": {"name": "Kuwait", "color": "#67e8f9", "role": "Inflow"},
    "OMN": {"name": "Oman", "color": "#0ea5e9", "role": "Inflow"},
    "KOR": {"name": "South Korea", "color": "#ef4444", "role": "Ultra-low fertility"},
    "TWN": {"name": "Taiwan", "color": "#fb7185", "role": "Ultra-low fertility"},
    "HKG": {"name": "Hong Kong", "color": "#f97316", "role": "Ultra-low fertility"},
    "JPN": {"name": "Japan", "color": "#f59e0b", "role": "Ultra-low fertility"},
}

STORY_CONFIGS = {
    "migration": {
        "label": "Migration hotspots",
        "indicator": "net_migration_rate",
        "eyebrow": "Migration hotspots",
        "title": "Low vs High Migration Rate",
        "copy": (
            "The Gulf and the Levant sit close together but tell opposite migration stories. "
            "Syria and Yemen show war-linked outflow; the Gulf economies show labor-market inflow."
        ),
        "isos": MIGRATION_OUTFLOW + MIGRATION_INFLOW,
        "origins": MIGRATION_OUTFLOW,
        "hosts": MIGRATION_INFLOW,
        "target": {"longitude": 47, "latitude": 23, "zoom": 1.32},
    },
    "fertility": {
        "label": "Ultra-low fertility",
        "indicator": "fertility_rate",
        "eyebrow": "Ultra-low fertility",
        "title": "Below Replacement in East Asia",
        "copy": (
            "To keep a population stable without immigration, fertility needs to sit near 2.1. "
            "East Asia's richest urban societies now sit far below that line."
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

    payload = payload[
        [
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
    ]
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
            class_="story-globe-pane",
        ),
        ui.div(
            ui.div(
                ui.output_ui("story_dashboard_header_text"),
                ui.input_action_button("close_story_panel", "Close", class_="story-panel-close"),
                class_="story-dashboard-header",
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
            ui.panel_conditional(
                "input.indicator == 'net_migration_rate'",
                ui.div(
                    story_intro(
                        "Two Migration Engines",
                        "Some people move because war pushes them out. Others move because labor markets pull them in. Syria and Yemen sit on the outflow side; the Gulf economies sit on the inflow side.",
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch corridor-origin"), " Outflow pressure"),
                        ui.span(ui.span(class_="corridor-swatch corridor-host"), " Labor-market inflow"),
                        class_="corridor-legend",
                    ),
                    ui.card(
                        ui.card_header("Net Migration Over Time"),
                        output_widget("migration_rate_lines"),
                    ),
                    story_intro(
                        "The Extremes",
                        "The same metric captures both halves of the story: negative shocks when people leave, and positive spikes where receiving economies absorb workers.",
                    ),
                    ui.card(
                        ui.card_header("Peak Migration Shock"),
                        output_widget("migration_peak_shocks"),
                    ),
                    class_="story-dashboard-body",
                ),
            ),
            ui.panel_conditional(
                "input.indicator == 'fertility_rate'",
                ui.div(
                    story_intro(
                        "Below Replacement",
                        "Replacement fertility is about 2.1 children per woman. South Korea, Taiwan, Hong Kong, and Japan all fall far below that benchmark.",
                        "The drivers are not one thing: urban housing costs, work culture, delayed marriage, and child-rearing expectations all compress family formation.",
                    ),
                    ui.div(
                        ui.span(ui.span(class_="corridor-swatch fertility-low"), " Ultra-low fertility"),
                        ui.span(ui.span(class_="corridor-swatch fertility-replacement"), " Replacement 2.1"),
                        class_="corridor-legend",
                    ),
                    ui.card(
                        ui.card_header("Fertility vs Replacement"),
                        output_widget("fertility_replacement_lines"),
                    ),
                    ui.card(
                        ui.card_header("Lowest Fertility Ranking"),
                        output_widget("fertility_lowest_ranking"),
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
    story_panel_open = reactive.Value(False)

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
        label = (
            "See the story charts about low vs high migration rate"
            if story_id == "migration"
            else "See the story charts about ultra-low birth rate (fertility)"
        )
        return ui.div(
            ui.input_action_button("open_story", label, class_="story-open-button"),
            class_="story-sidebar-block",
        )

    @render.ui
    def story_country_filter():
        story_id = active_story()
        if story_id not in STORY_CONFIGS:
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
        if active_story() not in STORY_CONFIGS:
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

    @render_widget
    def deep_dive_plot():
        iso = selected_country.get()
        fig = go.Figure()
        if not iso:
            return fig

        indicator = input.indicator()
        config = INDICATOR_CONFIG[indicator]
        country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
        if country_df.empty:
            return fig

        year = input.timeline_year()
        fig.add_scatter(
            x=country_df["year"],
            y=country_df[config["col"]],
            mode="lines",
            line=dict(color="#818cf8", width=2),
            name=config["label"],
            hovertemplate="%{x}<br>%{y:.2f}<extra></extra>",
        )
        fig.add_vline(x=year, line_width=2, line_dash="dash", line_color="#ef4444")
        fig.update_layout(
            title=None,
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
        fig.update_xaxes(title_text="Year", gridcolor="rgba(255,255,255,0.07)")
        fig.update_yaxes(title_text=config["unit"], gridcolor="rgba(255,255,255,0.07)")
        return fig

    def legend_bar(gradient: str, left: str, middle: str, right: str) -> ui.TagList:
        return ui.TagList(
            ui.div(
                style=(
                    "height: 12px; border-radius: 6px; "
                    f"background: {gradient}; "
                    "margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1);"
                )
            ),
            ui.div(
                ui.span(left, style="font-size: 0.8rem; color: #e2e8f0; font-weight: 600;"),
                ui.span(
                    middle,
                    style=(
                        "font-size: 0.8rem; color: #cbd5e1; font-weight: 600; "
                        "position: absolute; left: 50%; transform: translateX(-50%);"
                    ),
                ),
                ui.span(right, style="font-size: 0.8rem; color: #e2e8f0; font-weight: 600; float: right;"),
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
        fig.update_layout(
            title=None,
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=30, r=24, t=24, b=94),
            height=height,
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor="rgba(15, 23, 42, 0.96)",
                bordercolor="#818cf8",
                font=dict(color="#f8fafc", size=12),
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
                xanchor="left",
                x=0,
                bgcolor="rgba(15, 23, 42, 0.78)",
                bordercolor="rgba(255,255,255,0.10)",
                borderwidth=1,
                font=dict(color="#f8fafc", size=12),
            ),
        )
        fig.update_traces(hoverlabel=dict(bgcolor="rgba(15, 23, 42, 0.96)", font=dict(color="#f8fafc")))
        fig.update_xaxes(title_text="Year", title_standoff=12, gridcolor="rgba(255,255,255,0.07)")
        fig.update_yaxes(title_text=y_title, gridcolor="rgba(255,255,255,0.07)")
        return fig

    @render_widget
    def migration_rate_lines():
        if open_story_id() != "migration":
            return go.Figure()
        selected_isos = selected_story_isos()
        fig = go.Figure()
        add_conflict_shading(fig, [iso for iso in selected_isos if iso in MIGRATION_OUTFLOW])

        for iso in selected_isos:
            country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
            is_outflow = iso in MIGRATION_OUTFLOW
            fig.add_scatter(
                x=country_df["year"],
                y=country_df["net_migration_rate"],
                mode="lines",
                name=country_name(iso),
                line=dict(
                    color=COUNTRY_META[iso]["color"],
                    width=3 if is_outflow else 2.4,
                    dash="solid" if is_outflow else "dot",
                ),
            )

        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#94a3b8")
        return apply_story_layout(fig, "Migrants per 1,000 people", 420)

    @render_widget
    def migration_peak_shocks():
        if open_story_id() != "migration":
            return go.Figure()
        rows = []
        for iso in selected_story_isos():
            country_df = df_countries[df_countries["iso_alpha"].eq(iso)]
            if country_df.empty:
                continue
            if iso in MIGRATION_OUTFLOW:
                row = country_df.loc[country_df["net_migration_rate"].idxmin()]
                value_label = "Worst outflow"
            else:
                row = country_df.loc[country_df["net_migration_rate"].idxmax()]
                value_label = "Strongest inflow"
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
                "#ef4444" if row["iso"] in MIGRATION_OUTFLOW else "#22d3ee"
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

        if not df_world.empty:
            world = df_world.sort_values("year")
            fig.add_scatter(
                x=world["year"],
                y=world["fertility_rate"],
                mode="lines",
                name="World",
                line=dict(color="#e2e8f0", width=3, dash="dot"),
            )

        for iso in selected_isos:
            country_df = df_countries[df_countries["iso_alpha"].eq(iso)].sort_values("year")
            fig.add_scatter(
                x=country_df["year"],
                y=country_df["fertility_rate"],
                mode="lines",
                name=country_name(iso),
                line=dict(color=COUNTRY_META[iso]["color"], width=2.7),
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
            korea = df_countries[df_countries["iso_alpha"].eq("KOR")]
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

        return apply_story_layout(fig, "Children per woman", 420)

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


app = App(app_ui, server)
