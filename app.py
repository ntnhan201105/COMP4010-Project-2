"""
Demographic Stories Explorer Ă¢â‚¬â€ Python Shiny Dashboard
Run: python app.py  or  shiny run app.py --port 8000
"""
from pathlib import Path
from functools import lru_cache
from time import perf_counter
import pandas as pd
import numpy as np
import math
import json
from shiny import App, ui, reactive, render

# ── Monkey-patch: fix shinywidgets NaN serialization ──────────────
import shinywidgets._serialization as _sw_ser
import shinywidgets._comm as _sw_comm

def _clean_nan(obj):
    """Recursively replace NaN/inf with None."""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

_orig_pack = _sw_ser.json_packer
def _patched_packer(obj):
    return _orig_pack(_clean_nan(obj))

_sw_ser.json_packer = _patched_packer
_sw_comm.json_packer = _patched_packer
from shinywidgets import output_widget, render_widget
import plotly.graph_objects as go

from modules.data_loader import load_master_dataset, get_country_list
from modules.ml_clustering import (
    run_clustering, get_similar_countries,
    forecast_indicator, get_demographic_profile,
)
from modules.charts import (
    world_map_chart,
    animated_bubble_scatter, bubble_scatter_year, global_trend_lines,
    aging_line_chart, age_structure_stacked, elderly_ranking_bar,
    growth_line_chart, children_share_bar,
    migration_trend_chart, disruption_dashboard_chart,
    cluster_pca_scatter, similar_countries_radar,
    country_multi_line, country_forecast_chart, generate_country_insight,
    comparison_ranking_bar,
    forecast_multi_country, forecast_table, forecast_trend_bar,
    CLUSTER_COLORS, clean_template, set_theme_dark,
    # Story charts (Migration & Fertility)
    migration_story_lines, migration_peak_shocks,
    fertility_replacement_lines, fertility_lowest_ranking,
    MIGRATION_OUTFLOW, MIGRATION_INFLOW, FERTILITY_ISOS, STORY_META,
)

# Ă¢â€â‚¬Ă¢â€â‚¬ Globals Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
COUNTRIES = get_country_list()
AGING_DEFAULTS = ['Japan', 'South Korea', 'Italy', 'Germany', 'China']
GROWTH_DEFAULTS = ['Nigeria', 'Ethiopia', 'Tanzania', 'Pakistan', 'Democratic Republic of Congo']
MIGRATION_DEFAULTS = ['Ukraine', 'Syria', 'Afghanistan', 'Yemen']
FORECAST_DEFAULTS = ['Vietnam', 'Japan', 'Nigeria', 'Germany', 'India', 'Brazil']
FORECAST_INDICATORS = ['Median age', 'Fertility rate', 'Life expectancy', 'Population growth rate']

# War-torn / conflict-affected highlights Ă¢â‚¬â€ 4 flagship countries for demographic storytelling
# Each represents a distinct region & conflict type with clear demographic disruption visible in data
WAR_TORN = [
    'Ukraine',      # Europe Ă¢â‚¬â€ active war, mass displacement, population crash
    'Syria',        # Middle East Ă¢â‚¬â€ protracted civil war, refugee crisis, migrant stock spike
    'Afghanistan',  # Central Asia Ă¢â‚¬â€ decades of conflict, stuck at high fertility + low life expectancy
    'Yemen',        # Arabian Peninsula Ă¢â‚¬â€ active conflict, humanitarian crisis, demographic reversal
]

ENABLE_RENDER_TIMING = False


def _theme_key(dark: bool) -> int:
    return 1 if dark else 0


def _clone_fig(fig: go.Figure) -> go.Figure:
    return go.Figure(fig)


def _build_with_theme(dark_key: int, builder):
    set_theme_dark(bool(dark_key))
    return builder()


def _timed(name: str, builder):
    if not ENABLE_RENDER_TIMING:
        return builder()
    start = perf_counter()
    out = builder()
    elapsed = (perf_counter() - start) * 1000
    if elapsed > 120:
        print(f"[render] {name}: {elapsed:.0f} ms")
    return out


@lru_cache(maxsize=256)
def _cached_world_map(year: int, indicator: str, highlight_war_torn: bool, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: world_map_chart(
            year=year,
            indicator=indicator,
            compact=True,
            highlight_war_torn=highlight_war_torn,
        ),
    )


@lru_cache(maxsize=256)
def _cached_home_cluster_mix(year: int, dark_key: int):
    def _build():
        clusters = run_clustering(year=year)
        order = list(CLUSTER_COLORS.keys())
        counts = clusters['Cluster Label'].value_counts().reindex(order, fill_value=0)
        fig = go.Figure(go.Bar(
            x=counts.values,
            y=counts.index,
            orientation='h',
            marker=dict(color=[CLUSTER_COLORS[label] for label in counts.index]),
            text=counts.values,
            textposition='outside',
            hovertemplate='%{y}<br>%{x} countries<extra></extra>',
        ))
        fig.update_layout(
            title=None,
            height=210,
            margin=dict(l=10, r=38, t=8, b=24),
            xaxis_title='Countries',
            yaxis_title='',
            xaxis=dict(range=[0, max(70, int(counts.max()) + 10)]),
        )
        fig.update_yaxes(autorange='reversed')
        return clean_template(fig)
    return _build_with_theme(dark_key, _build)


@lru_cache(maxsize=512)
def _cached_comparison_ranking(indicator: str, year: int, top_n: int, color_scale: str, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: comparison_ranking_bar(indicator, year=year, top_n=top_n, color_scale=color_scale),
    )


@lru_cache(maxsize=256)
def _cached_bubble_scatter(year: int, highlight_war_torn: bool, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: bubble_scatter_year(year, highlight_war_torn=highlight_war_torn),
    )


@lru_cache(maxsize=256)
def _cached_elderly_ranking(year: int, dark_key: int):
    return _build_with_theme(dark_key, lambda: elderly_ranking_bar(year=year))


@lru_cache(maxsize=256)
def _cached_children_share(year: int, dark_key: int):
    return _build_with_theme(dark_key, lambda: children_share_bar(year=year))


@lru_cache(maxsize=512)
def _cached_age_structure(country: str, dark_key: int):
    return _build_with_theme(dark_key, lambda: age_structure_stacked(country))


@lru_cache(maxsize=512)
def _cached_country_forecast(country: str, indicator: str, dark_key: int):
    return _build_with_theme(dark_key, lambda: country_forecast_chart(country, indicator))


@lru_cache(maxsize=256)
def _cached_country_multi_line(country: str, compare_countries: tuple, dark_key: int):
    compare = list(compare_countries) if compare_countries else None
    return _build_with_theme(dark_key, lambda: country_multi_line(country, compare))


@lru_cache(maxsize=64)
def _cached_global_trends(compact: bool, dark_key: int):
    return _build_with_theme(dark_key, lambda: global_trend_lines(compact=compact))


@lru_cache(maxsize=256)
def _cached_aging_line(countries: tuple, dark_key: int):
    return _build_with_theme(dark_key, lambda: aging_line_chart(list(countries)))


@lru_cache(maxsize=256)
def _cached_growth_line(countries: tuple, dark_key: int):
    return _build_with_theme(dark_key, lambda: growth_line_chart(list(countries)))


@lru_cache(maxsize=256)
def _cached_migration_trend(countries: tuple, highlight_war_torn: bool, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: migration_trend_chart(list(countries), highlight_war_torn=highlight_war_torn),
    )


@lru_cache(maxsize=256)
def _cached_forecast_lines(countries: tuple, indicator: str, forecast_years: int, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: forecast_multi_country(list(countries), indicator=indicator, forecast_years=forecast_years),
    )


@lru_cache(maxsize=128)
def _cached_forecast_trend(indicator: str, top_n: int, forecast_years: int, ascending: bool, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: forecast_trend_bar(
            indicator=indicator,
            top_n=top_n,
            forecast_years=forecast_years,
            ascending=ascending,
        ),
    )


@lru_cache(maxsize=256)
def _cached_forecast_table(countries: tuple, indicator: str, forecast_years: int, target_years: tuple, dark_key: int):
    return _build_with_theme(
        dark_key,
        lambda: forecast_table(
            list(countries),
            indicator=indicator,
            forecast_years=forecast_years,
            target_years=list(target_years),
        ),
    )


# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
# CSS
# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body { font-family: 'Inter', sans-serif; background: #f0f2f5; }

.page-shell { padding: 1.25rem 1rem 2rem; max-width: 100%; margin: 0 auto; }
.home-shell { padding: 0.85rem 0.65rem 1.25rem; }

.hero-band {
    background: linear-gradient(135deg, #10253f 0%, #1e3a5f 52%, #2f5f73 100%);
    color: #fff; border-radius: 14px; padding: 1.35rem 1.5rem;
    margin-bottom: 1rem; box-shadow: 0 12px 28px rgba(16,37,63,0.18);
}
.hero-kicker { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.8; font-weight: 700; }
.hero-title { font-size: 1.85rem; line-height: 1.15; font-weight: 800; margin: 0.25rem 0 0.35rem; }
.hero-copy { max-width: 860px; color: rgba(255,255,255,0.84); font-size: 0.98rem; margin: 0; }

.metric-grid {
    display: grid; grid-template-columns: repeat(5, minmax(150px, 1fr));
    gap: 0.85rem; margin: 0.85rem 0 1rem;
}
.metric-card {
    background: #fff; border: 1px solid #dde4ea; border-radius: 10px;
    padding: 0.9rem 1rem; box-shadow: 0 2px 8px rgba(16,37,63,0.06);
}
.metric-card .metric-label { font-size: 0.72rem; color: #667085; text-transform: uppercase; font-weight: 700; }
.metric-card .metric-value { font-size: 1.55rem; font-weight: 800; color: #172b45; margin-top: 0.15rem; }
.metric-card .metric-note { font-size: 0.78rem; color: #667085; margin-top: 0.2rem; line-height: 1.3; }

.insight-strip {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.85rem;
    margin: 0.25rem 0 1rem;
}
.insight-pill {
    background: #fff; border-left: 4px solid #1e3a5f; border-radius: 8px;
    padding: 0.85rem 1rem; box-shadow: 0 1px 5px rgba(16,37,63,0.06);
}
.insight-pill strong { display:block; color:#172b45; font-size:0.92rem; margin-bottom:0.25rem; }
.insight-pill span { color:#667085; font-size:0.82rem; line-height:1.35; }

.chart-grid-main {
    display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(420px, 0.95fr);
    gap: 0.75rem; align-items: start;
}
.chart-left-stack {
    display: grid; grid-auto-rows: auto; gap: 0.75rem;
}
.chart-right-stack {
    display: grid; grid-auto-rows: auto; gap: 0.75rem;
}
.animation-controls {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;
    margin: 0.65rem 0 0.8rem;
}
.animation-status {
    font-size: 0.76rem; color: #667085; line-height: 1.35;
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 0.55rem 0.65rem; margin-bottom: 0.75rem;
}
.chart-stack { display: grid; grid-template-rows: auto auto; gap: 1rem; }
.section-note {
    background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #2f5f73;
    border-radius: 8px; padding: 0.75rem 0.9rem; margin: 0.5rem 0 0.85rem;
    color: #475467; font-size: 0.86rem; line-height: 1.45;
}
.section-note strong { color: #172b45; }
.control-row {
    display: flex; gap: 1rem; align-items: end; flex-wrap: wrap; margin-bottom: 0.6rem;
}
.control-row > * { min-width: 220px; flex: 1; }

/* Navbar */
.navbar { background: #1e3a5f !important; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
.navbar .navbar-brand { color: #fff !important; font-weight: 700; }
.navbar .nav-link { color: rgba(255,255,255,0.85) !important; font-weight: 500; }
.navbar .nav-link.active { color: #fff !important; background: rgba(255,255,255,0.15) !important; border-radius: 6px; }

/* Value boxes */
.bslib-value-box { border-radius: 10px !important; }

/* Cards */
.card { border-radius: 10px; border: 1px solid #e0e0e0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card-header { font-weight: 600; font-size: 0.95rem; background: #fff; border-bottom: 1px solid #eee; }
.home-shell .card-header { padding: 0.55rem 0.75rem; font-size: 0.86rem; }
.home-shell .card-body { padding: 0.55rem 0.65rem 0.65rem; }
.home-shell .metric-grid { gap: 0.65rem; margin: 0.5rem 0 0.75rem; }
.home-shell .metric-card { padding: 0.65rem 0.8rem; }
.home-shell .metric-card .metric-value { font-size: 1.34rem; }

/* Sidebar */
.sidebar { background: #fff; border-right: 1px solid #e0e0e0; }

/* Finding click cards */
.finding-card {
    background: #fff; border: 1px solid #e0e0e0; border-radius: 10px;
    padding: 1.2rem; cursor: pointer; text-align: center;
    transition: all 0.2s; height: 100%;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.finding-card:hover {
    border-color: #1e3a5f; transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(30,58,95,0.15);
}
.finding-card .card-icon {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 54px; height: 24px; padding: 0 0.55rem; border-radius: 999px;
    background: #eef4f8; color: #1e3a5f; font-size: 0.72rem;
    font-weight: 800; text-transform: uppercase; margin-bottom: 0.45rem;
}
.finding-card .card-title { font-weight: 600; font-size: 0.9rem; color: #222; margin-bottom: 0.2rem; }
.finding-card .card-num { font-size: 1.6rem; font-weight: 700; color: #1e3a5f; margin: 0.3rem 0; }
.finding-card .card-sub { font-size: 0.78rem; color: #888; line-height: 1.3; }
.evidence-grid {
    display: grid; grid-template-columns: repeat(5, minmax(150px, 1fr));
    gap: 0.85rem;
}
.story-grid {
    display: grid; grid-template-columns: repeat(4, minmax(190px, 1fr));
    gap: 0.75rem; margin: 0 0 0.85rem;
}
.story-heading {
    margin: 0 0 0.5rem; color: #172b45; font-size: 1rem; font-weight: 800;
}
.story-note {
    margin: -0.2rem 0 0.65rem; color: #667085; font-size: 0.84rem;
}

.compact-kpi-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
    gap: 0.75rem; margin: 0.75rem auto 1rem; max-width: 100%;
}
.compact-kpi-card {
    background: #fff; border: 1px solid #dde4ea; border-radius: 9px;
    padding: 0.75rem 0.9rem; text-align: left;
    box-shadow: 0 1px 5px rgba(16,37,63,0.05);
}
.compact-kpi-title { font-size: 0.72rem; color: #475467; font-weight: 800; text-transform: uppercase; }
.compact-kpi-value { font-size: 0.96rem; color: #172b45; font-weight: 750; margin-top: 0.25rem; line-height: 1.35; }
.kpi-stat-lines { margin-top: 0.3rem; line-height: 1.5; font-size: 0.85rem; color: #172b45; font-weight: 550; }
.cluster-pill {
    display: inline-block; padding: 0.35rem 0.65rem; border-radius: 999px;
    background: #f2ecfb; color: #7d3fb2; font-weight: 800;
    font-size: 1rem; line-height: 1.2;
}

@media (max-width: 1100px) {
    .metric-grid { grid-template-columns: repeat(2, minmax(160px, 1fr)); }
    .insight-strip { grid-template-columns: 1fr; }
    .chart-grid-main { grid-template-columns: 1fr; }
    .chart-left-stack { grid-template-columns: 1fr; }
    .chart-stack { grid-template-rows: auto; }
    .chart-right-stack { grid-template-columns: repeat(2, 1fr); }
    .story-grid { grid-template-columns: 1fr; }
    .evidence-grid { grid-template-columns: repeat(2, minmax(160px, 1fr)); }
}

@media (max-width: 640px) {
    .page-shell { padding: 1rem; }
    .hero-title { font-size: 1.45rem; }
    .metric-grid { grid-template-columns: 1fr; }
    .evidence-grid { grid-template-columns: 1fr; }
}

.shiny-output-output_widget.recalculating,
.shiny-output-output_ui.recalculating {
    background: transparent;
}
.shiny-output-output_widget.recalculating iframe {
    opacity: 1;
}

/* Sidebar quick-stats */
.sidebar-quick-stat {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.45rem 0; border-bottom: 1px solid #f0f0f0;
    font-size: 0.85rem;
}
.sidebar-quick-stat:last-child { border-bottom: none; }
.sidebar-quick-stat .sqs-label { color: #667085; }
.sidebar-quick-stat .sqs-value { font-weight: 700; color: #172b45; }

/* KPI banner */
.kpi-banner {
    display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center;
    padding: 1rem 0;
}
.kpi-item {
    text-align: center; min-width: 110px;
}
.kpi-item .kpi-num { font-size: 1.5rem; font-weight: 700; }
.kpi-item .kpi-lbl { font-size: 0.72rem; color: #888; text-transform: uppercase; }

/* Split view */
.split-shell {
    padding: 0.8rem 1rem 1rem;
    height: calc(100vh - 66px);
    min-height: 760px;
}
.split-grid {
    display: grid;
    grid-template-columns: minmax(480px, 42vw) minmax(0, 1fr);
    gap: 1rem;
    height: 100%;
}
.split-globe-panel {
    position: sticky;
    top: 0.75rem;
    height: calc(100vh - 86px);
    min-height: 720px;
    background: #0b1630;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 14px 32px rgba(16,37,63,0.18);
}
#split-globe-container { width: 100%; height: 100%; }
/* Globe sidebar */
.bslib-sidebar-layout > .collapse-toggle {
    display: none !important;
}
.sidebar.globe-sidebar {
    padding: 0 !important;
    background: #0b1630 !important;
    border-right: 0 !important;
    box-shadow: none !important;
    overflow: hidden !important;
}
#globe-container {
    width: 100%;
    height: calc(100vh - 60px);
    min-height: 500px;
}
.globe-status-overlay {
    position: absolute;
    left: 1rem;
    right: 4rem;
    top: 1rem;
    z-index: 14;
    pointer-events: none;
    color: #fff;
}
.globe-overlay-kicker {
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.5rem;
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 999px;
    background: rgba(8, 20, 48, 0.45);
    color: rgba(255,255,255,0.76);
    backdrop-filter: blur(10px);
    font-size: 0.68rem;
    line-height: 1;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    font-weight: 850;
}
.globe-overlay-title {
    margin-top: 0.45rem;
    font-size: clamp(1.15rem, 1.5vw, 1.55rem);
    line-height: 1.08;
    font-weight: 900;
    text-shadow: 0 8px 22px rgba(0,0,0,0.4);
}
.globe-overlay-chip {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.55rem;
    padding: 0.48rem 0.62rem;
    max-width: min(440px, 100%);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 10px;
    background: rgba(11, 22, 48, 0.66);
    box-shadow: 0 10px 28px rgba(0,0,0,0.28);
    backdrop-filter: blur(14px);
}
.globe-overlay-country {
    color: #fff;
    font-size: 0.9rem;
    font-weight: 850;
}
.globe-overlay-meta {
    color: rgba(255,255,255,0.68);
    font-size: 0.74rem;
    font-weight: 650;
}
.globe-overlay-warning {
    color: #fecaca;
    background: rgba(185, 28, 28, 0.34);
    border: 1px solid rgba(248, 113, 113, 0.35);
    border-radius: 999px;
    padding: 0.2rem 0.42rem;
    font-size: 0.68rem;
    font-weight: 850;
}
.globe-controls-toggle {
    position: absolute; top: 0.85rem; right: 0.85rem; z-index: 20;
    background: rgba(11,22,48,0.72); border: 1px solid rgba(255,255,255,0.24);
    color: #fff; border-radius: 10px; cursor: pointer;
    font-size: 1rem; width: 38px; height: 38px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s, transform 0.15s, border-color 0.2s;
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 22px rgba(0,0,0,0.28);
}
.globe-controls-toggle:hover {
    background: rgba(22,34,66,0.92);
    border-color: rgba(255,255,255,0.42);
    transform: translateY(-1px);
}
.globe-controls-popup {
    position: absolute; top: 0.85rem; right: 3.65rem; z-index: 18;
    width: 305px; max-height: calc(100% - 1.7rem);
    background: linear-gradient(180deg, rgba(18,31,62,0.94) 0%, rgba(11,22,48,0.9) 100%);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 14px; padding: 1rem;
    backdrop-filter: blur(18px);
    box-shadow: 0 18px 48px rgba(0,0,0,0.52);
    overflow-y: auto;
    transition: opacity 0.2s, transform 0.2s;
}
.globe-controls-popup.collapsed {
    display: none;
}
.globe-controls-popup .shiny-input-container { margin-bottom: 0.5rem; }
.globe-controls-popup .shiny-input-container label {
    color: #cbd5e1; font-size: 0.74rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.04em;
}
.globe-controls-popup hr { border-color: rgba(255,255,255,0.12); margin: 0.5rem 0; }
.split-globe-overlay {
    position: absolute;
    left: 1rem;
    right: 1rem;
    top: 1rem;
    z-index: 3;
    pointer-events: none;
    color: #fff;
}
.split-globe-kicker { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.72; font-weight: 800; }
.split-globe-title { font-size: 1.35rem; font-weight: 850; line-height: 1.15; margin-top: 0.2rem; }
.split-globe-note { margin-top: 0.35rem; max-width: 440px; color: rgba(255,255,255,0.72); font-size: 0.82rem; line-height: 1.35; }
.split-dashboard {
    min-width: 0;
    overflow-y: auto;
    padding-right: 0.15rem;
}
.split-controls {
    display: grid;
    grid-template-columns: minmax(170px, 0.7fr) minmax(210px, 1fr) minmax(240px, 1.1fr);
    gap: 0.85rem;
    align-items: end;
    margin-bottom: 0.85rem;
}
.split-selected-band {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: #fff;
    border: 1px solid #dde4ea;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 2px 8px rgba(16,37,63,0.06);
}
.split-selected-name { font-size: 1.3rem; font-weight: 850; color: #172b45; line-height: 1.1; }
.split-selected-meta { margin-top: 0.2rem; font-size: 0.82rem; color: #667085; }
.split-badge {
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
    border-radius: 999px;
    padding: 0.35rem 0.65rem;
    background: #fff0f0;
    color: #b42318;
    font-weight: 800;
    font-size: 0.76rem;
}
.globe-link-btn {
    border: 1px solid #c7d7e8;
    background: #f8fbff;
    color: #1e3a5f;
    border-radius: 8px;
    padding: 0.42rem 0.65rem;
    font-size: 0.78rem;
    font-weight: 800;
    cursor: pointer;
    transition: all 0.15s ease;
}
.globe-link-btn:hover {
    background: #eef6ff;
    border-color: #5b9bd5;
    transform: translateY(-1px);
}
.globe-link-row {
    display: flex;
    justify-content: flex-end;
    margin: -0.15rem 0 0.45rem;
}
.split-chart-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
}
.split-chart-grid .card:first-child { grid-column: span 2; }
.split-globe-tooltip {
    background: #101828 !important;
    color: #fff !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    border-radius: 8px !important;
    padding: 10px 12px !important;
    box-shadow: 0 10px 28px rgba(0,0,0,0.4) !important;
    font-family: Inter, sans-serif !important;
}
.split-globe-tooltip-title { color: #93c5fd; font-weight: 800; margin-bottom: 0.25rem; }
.split-globe-tooltip-row { color: #cbd5e1; font-size: 0.82rem; line-height: 1.35; }

@media (max-width: 1180px) {
    .split-shell { height: auto; min-height: 0; }
    .split-grid { grid-template-columns: 1fr; height: auto; }
    .split-globe-panel { position: relative; height: 520px; min-height: 520px; }
    .split-controls { grid-template-columns: 1fr; }
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f0f0f0; }
::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

/* Ă¢â€â‚¬Ă¢â€â‚¬ Dark mode toggle Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬ */
.theme-toggle {
    position: fixed; top: 0.6rem; right: 1.2rem; z-index: 9999;
    display: flex; align-items: center; gap: 0.4rem;
    background: rgba(255,255,255,0.15); border-radius: 20px;
    padding: 0.3rem 0.3rem; cursor: pointer; border: none;
    color: #fff; font-size: 0.82rem; font-weight: 600;
    transition: background 0.2s;
}
.theme-toggle:hover { background: rgba(255,255,255,0.28); }
.theme-toggle .icon-slot { font-size: 1.05rem; line-height: 1; }

/* Ă¢â€â‚¬Ă¢â€â‚¬ Dark theme overrides Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬ */
[data-theme="dark"] {
    --bg: #16181d;
    --surface: #1e2130;
    --surface2: #262a36;
    --border: #2e3342;
    --text: #d5d7e0;
    --text-muted: #8b8fa3;
    --text-heading: #e8eaef;
    --brand: #1e3a5f;
    --accent: #5b9bd5;
}
[data-theme="dark"] body { background: var(--bg); color: var(--text); }
[data-theme="dark"] .navbar { background: var(--surface) !important; }
[data-theme="dark"] .sidebar { background: var(--surface); border-right-color: var(--border); }
[data-theme="dark"] .card { background: var(--surface); border-color: var(--border); box-shadow: 0 1px 4px rgba(0,0,0,0.25); }
[data-theme="dark"] .card-header { background: var(--surface2); border-bottom-color: var(--border); color: var(--text-heading); }
[data-theme="dark"] .metric-card { background: var(--surface); border-color: var(--border); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
[data-theme="dark"] .metric-card .metric-value { color: #e0e4f0; }
[data-theme="dark"] .metric-card .metric-label { color: var(--text-muted); }
[data-theme="dark"] .metric-card .metric-note { color: var(--text-muted); }
[data-theme="dark"] .insight-pill { background: var(--surface); border-left-color: var(--accent); }
[data-theme="dark"] .insight-pill strong { color: var(--text-heading); }
[data-theme="dark"] .insight-pill span { color: var(--text-muted); }
[data-theme="dark"] .section-note { background: var(--surface2); border-color: var(--border); color: var(--text-muted); }
[data-theme="dark"] .section-note strong { color: var(--text-heading); }
[data-theme="dark"] .compact-kpi-card { background: var(--surface); border-color: var(--border); }
[data-theme="dark"] .compact-kpi-title { color: var(--text-muted); }
[data-theme="dark"] .compact-kpi-value { color: var(--text-heading); }
[data-theme="dark"] .kpi-stat-lines { color: var(--text); }
[data-theme="dark"] .finding-card { background: var(--surface); border-color: var(--border); }
[data-theme="dark"] .finding-card:hover { border-color: var(--accent); }
[data-theme="dark"] .finding-card .card-title { color: var(--text-heading); }
[data-theme="dark"] .finding-card .card-sub { color: var(--text-muted); }
[data-theme="dark"] .story-heading { color: var(--text-heading); }
[data-theme="dark"] .story-note { color: var(--text-muted); }
[data-theme="dark"] .compact-kpi-value { color: var(--text-heading); }
[data-theme="dark"] .control-row { color: var(--text); }
[data-theme="dark"] ::-webkit-scrollbar-track { background: var(--surface); }
[data-theme="dark"] ::-webkit-scrollbar-thumb { background: #444; }
[data-theme="dark"] .kpi-item .kpi-lbl { color: var(--text-muted); }
[data-theme="dark"] .kpi-item .kpi-num { color: var(--text-heading); }
[data-theme="dark"] .split-selected-band { background: var(--surface); border-color: var(--border); }
[data-theme="dark"] .split-selected-name { color: var(--text-heading); }
[data-theme="dark"] .split-selected-meta { color: var(--text-muted); }
[data-theme="dark"] .split-dashboard { color: var(--text); }
[data-theme="dark"] .globe-link-btn { background: var(--surface2); border-color: var(--border); color: #cfe6ff; }
[data-theme="dark"] .globe-link-btn:hover { border-color: var(--accent); background: #243044; }
"""


# Ă¢â€â‚¬Ă¢â€â‚¬ Helper functions Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
def _card(title: str, *content, **kwargs):
    """Wrap content in a Shiny card with header."""
    return ui.card(
        ui.card_header(title),
        ui.card_body(*content),
        **kwargs,
    )


def finding_click_card(target_tab: str, icon: str, number: str, title: str, subtitle: str):
    return ui.tags.div(
        ui.tags.div(icon, class_="card-icon"),
        ui.tags.div(number, class_="card-num"),
        ui.tags.div(title, class_="card-title"),
        ui.tags.div(subtitle, class_="card-sub"),
        class_="finding-card",
        onclick=f"Shiny.setInputValue('navigate_to', '{target_tab}', {{priority: 'event'}})",
    )


def globe_handoff_button(input_id: str, label: str = "View on Globe"):
    return ui.tags.div(
        ui.input_action_button(input_id, label, class_="globe-link-btn"),
        class_="globe-link-row",
    )


# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
# UI
# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â


# ─── Precomputed globe payloads (globevis-style performance optimisation) ───
# Colour helper functions lifted to module level so _split_globe_payload can use @lru_cache

def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.strip().lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _blend(c1, c2, t):
    t = max(0, min(1, float(t)))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _value_color(value, indicator):
    if pd.isna(value):
        return (180, 190, 200)
    if indicator == "Population":
        t = np.log10(max(float(value), 1)) / 10
        return _blend((219, 234, 254), (37, 99, 235), t)
    if indicator == "Fertility rate":
        t = (float(value) - 1) / 6
        return _blend((6, 200, 240), (240, 36, 160), t)
    if indicator == "Life expectancy":
        t = (float(value) - 40) / 45
        return _blend((239, 68, 68), (16, 217, 122), t)
    if indicator == "Median age":
        t = (float(value) - 15) / 35
        return _blend((125, 211, 252), (124, 58, 237), t)
    if indicator == "Population growth rate":
        t = (float(value) + 3) / 7
        return _blend((239, 68, 68), (34, 197, 94), t)
    if indicator == "Elderly share (%)":
        t = float(value) / 35
        return _blend((254, 226, 226), (185, 28, 28), t)
    if indicator == "Children share (%)":
        t = float(value) / 55
        return _blend((220, 252, 231), (21, 128, 61), t)
    if indicator in ("net_migration_rate", "Migration rate"):
        # Diverging: red (emigration) → neutral → cyan (immigration)
        mag = np.log1p(min(abs(float(value)), 100000)) / np.log1p(100000)
        if float(value) < 0:
            return _blend((22, 32, 52), (240, 40, 40), mag)
        else:
            return _blend((22, 32, 52), (0, 210, 255), mag)
    if indicator == "child_mortality":
        # Green (low) → yellow → red (high): 0% → 10% → 25%
        t = min(float(value) / 25, 1.0)
        return _blend((34, 197, 94), (239, 68, 68), t)
    if indicator == "death_rate":
        # Green (low) → yellow → red (high): 2 → 10 → 20
        t = (min(float(value), 20) - 2) / 18
        return _blend((34, 197, 94), (239, 68, 68), t)
    return (90, 140, 210)

@lru_cache(maxsize=512)
def _split_globe_payload(year, indicator):
    """Cached globe colour payload — computed once per (year, indicator) pair."""
    year = int(year)
    # Map indicator key → dataframe column
    col_map = {
        "net_migration_rate": "Net migration rate",
        "fertility_rate": "Fertility rate",
        "life_expectancy": "Life expectancy",
        "child_mortality": "Child mortality rate",
        "death_rate": "Death rate",
    }
    col = col_map.get(indicator, indicator)
    df = load_master_dataset()
    df_year = df[(df["Year"] == year) & df["Code"].notna()].copy()
    df_year = df_year[
        ~df_year["Code"].str.startswith("OWID").fillna(False)
        & (df_year["Code"].str.len() == 3)
    ]
    clusters = run_clustering(year=year)
    df_year = df_year.merge(clusters[["Entity", "Cluster Label"]], on="Entity", how="left")

    rows = []
    for _, r in df_year.iterrows():
        if indicator in ("Demographic Cluster", "Cluster Label"):
            label = r.get("Cluster Label")
            rgb = _hex_to_rgb(CLUSTER_COLORS.get(label, "#94a3b8"))
            raw_value = label if pd.notna(label) else "-"
        else:
            raw_value = r.get(col) if col in r.index else None
            if pd.isna(raw_value):
                raw_value = None
                rgb = (90, 140, 210)
            else:
                rgb = _value_color(float(raw_value), indicator)
        rows.append({
            "country": r["Entity"],
            "iso_alpha": r["Code"],
            "color_r": int(rgb[0]),
            "color_g": int(rgb[1]),
            "color_b": int(rgb[2]),
            "population": float(r["Population"]) if pd.notna(r.get("Population")) else 0,
            "raw_value": raw_value if raw_value is None or isinstance(raw_value, str) else (float(raw_value) if not (isinstance(raw_value, float) and np.isnan(raw_value)) else None),
            "is_war_torn": r["Entity"] in WAR_TORN,
        })
    return rows

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.tags.div(
            # Globe area — top ~70%, contains canvas + overlays
            ui.tags.div(
                ui.tags.div(id="globe-container"),
                # Status overlay on globe
                ui.tags.div(
                    ui.tags.div("Demographic Globe", class_="globe-overlay-kicker"),
                    ui.output_ui("globe_overlay_badge"),
                    class_="globe-status-overlay",
                ),
                # Deep Dive panel — floating overlay when country clicked
                ui.output_ui("deep_dive_panel"),
                # 2D/3D toggle — bottom-left of globe
                ui.tags.button(
                    ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px;"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg>2D Map'),
                    id="globe-view-toggle",
                    title="Toggle 2D / 3D view",
                ),
                # Map legend — floating bottom-right of globe
                ui.tags.div(
                    ui.output_ui("globe_legend_ui"),
                    class_="globe-legend-overlay",
                ),
                class_="globe-area",
            ),
            # Fixed bottom control panel — compact
            ui.tags.div(
                ui.tags.div(
                    ui.input_selectize("country_group", None,
                        choices={"global": "Global overview", "migration": "Migration hotspots", "fertility": "Ultra-low fertility"},
                        selected="global"),
                    style="flex:1; min-width:0;",
                ),
                ui.tags.div(
                    ui.input_slider("globe_year", None, 1950, 2023, 2023, step=1, sep="",
                                   animate=ui.AnimationOptions(interval=260, loop=False)),
                    style="flex:2; min-width:0;",
                ),
                ui.tags.div(
                    ui.input_selectize("globe_indicator", None,
                        choices={
                            "net_migration_rate": "★ Migration Rate",
                            "fertility_rate": "★ Fertility Rate",
                            "life_expectancy": "Life Expectancy",
                            "child_mortality": "Child Mortality",
                            "death_rate": "Death Rate",
                        },
                        selected="net_migration_rate"),
                    style="flex:1.5; min-width:0;",
                ),
                style="display:flex; gap:0.4rem; align-items:end;",
                class_="control-row-compact",
            ),
            # Story extras — only visible when ★ lens selected
            ui.tags.div(
                ui.output_ui("story_button_ui"),
                ui.output_ui("story_focus_ui"),
                id="story-extras",
                style="padding:0.3rem 0.65rem 0;",
            ),
            class_="globe-shell",
        ),
        width="38vw",
        open="always",
        resizable=True,
        class_="globe-sidebar",
        style="padding:0; position:relative; overflow:hidden;",
    ),
    ui.head_content(
        ui.tags.style(custom_css),
        ui.include_css("www/custom.css"),
        ui.include_js("www/dashboard.js"),
        ui.include_js("www/split_globe_bundle.js"),
        ui.tags.script("""
            (function() {
                const html = document.documentElement;
                const saved = localStorage.getItem('demo-theme');
                if (saved === 'dark') html.setAttribute('data-theme', 'dark');
                else html.setAttribute('data-theme', 'light');

                function pushThemeToShiny() {
                    if (window.Shiny) {
                        Shiny.setInputValue('dark_mode', html.getAttribute('data-theme') === 'dark', {priority: 'event'});
                    }
                }

                function toggleTheme() {
                    const cur = html.getAttribute('data-theme');
                    const next = cur === 'dark' ? 'light' : 'dark';
                    html.setAttribute('data-theme', next);
                    localStorage.setItem('demo-theme', next);
                    pushThemeToShiny();
                }

                // Expose toggle function globally so the button can call it
                window._toggleDarkMode = toggleTheme;

                // Listen for system preference changes
                window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
                    if (!localStorage.getItem('demo-theme')) {
                        html.setAttribute('data-theme', e.matches ? 'dark' : 'light');
                        pushThemeToShiny();
                    }
                });

                document.addEventListener('shiny:connected', pushThemeToShiny);
            })();
        """),
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 1: HOME Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    # Theme toggle -- fixed position, always visible regardless of tab
    ui.tags.button(
        ui.tags.span(ui.HTML("&#9790;"), class_="icon-slot"),
        ui.tags.span("Theme"),
        class_="theme-toggle",
        onclick="window._toggleDarkMode();",
    ),

    ui.navset_bar(
        ui.nav_panel("Overview",
            ui.tags.div(
                ui.tags.section(
                    ui.tags.div("Global demographic story", class_="home-intro-kicker"),
                    ui.tags.div(
                        ui.tags.div(
                            ui.tags.h1("One transition, three futures.", class_="home-intro-title"),
                            ui.tags.p(
                                "Fertility is falling and longevity is rising, but countries are not moving together. "
                                "Use the overview to choose a focused evidence path.",
                                class_="home-intro-copy",
                            ),
                            class_="home-intro-copyblock",
                        ),
                        ui.tags.div(
                            ui.tags.div("1950-2023", class_="home-intro-stat"),
                            ui.tags.div("long-run country panel", class_="home-intro-label"),
                            class_="home-intro-badge",
                        ),
                        class_="home-intro-inner",
                    ),
                    class_="home-intro",
                ),
                ui.output_ui("home_kpis"),
                ui.tags.div(
                    ui.tags.div("Choose one evidence path", class_="story-heading"),
                    ui.tags.div("Each path keeps the dashboard to a small set of figures, so the page reads like an argument instead of a chart dump.", class_="story-note"),
                    ui.tags.div(
                        finding_click_card(
                            "Migration",
                            "Conflict",
                            "4 countries",
                            "War & Disruption",
                            "Conflict bends migration, growth, mortality, and longevity trends.",
                        ),
                        finding_click_card(
                            "Aging Societies",
                            "Aging",
                            "5 countries",
                            "Low Fertility Futures",
                            "Ultra-low fertility shifts pressure toward care, pensions, and labor supply.",
                        ),
                        finding_click_card(
                            "ML Analysis",
                            "Clusters",
                            "4 groups",
                            "Similar Futures",
                            "Countries with similar demographic futures are not always geographic neighbors.",
                        ),
                        finding_click_card(
                            "Country Explorer",
                            "Globe",
                            "Live link",
                            "Country Explorer",
                            "Use the left globe, then inspect the selected country in detail.",
                        ),
                        class_="story-grid",
                    ),
                ),
                ui.tags.div(
                    ui.tags.div(
                        _card("World Map", output_widget("world_map")),
                        _card("Top Elderly Share", output_widget("home_elderly_ranking")),
                        class_="chart-left-stack",
                    ),
                    ui.tags.div(
                        _card("Global Trends 1950-2023", output_widget("home_global_trends")),
                        _card("Cluster Mix", output_widget("home_cluster_mix")),
                        class_="chart-right-stack",
                    ),
                    class_="chart-grid-main",
                ),
                class_="page-shell home-shell",
            ),
        value="Home",
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 2: GLOBAL TRANSITION Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    
    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 3: AGING SOCIETIES Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    ui.nav_panel("Aging Futures",
        ui.tags.div(
            ui.tags.h3("Low Fertility & Aging Futures", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Decision lens: "),
                "this story follows low-fertility countries where fewer births and longer lives shift pressure toward care systems, pensions, and labor supply.",
                class_="section-note",
            ),
            ui.output_ui("aging_kpis"),
            ui.layout_columns(
                _card("Fertility Rate & Median Age",
                    ui.input_selectize("aging_countries", "", choices=COUNTRIES, selected=AGING_DEFAULTS, multiple=True),
                    output_widget("aging_lines"),
                ),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Age Structure",
                    ui.input_selectize("aging_country_pick", "", choices=COUNTRIES, selected='Japan'),
                    globe_handoff_button("aging_pick_view_globe"),
                    output_widget("age_structure")),
                _card("Median Age Forecast",
                    ui.input_selectize("aging_forecast_country", "", choices=COUNTRIES, selected='Japan'),
                    globe_handoff_button("aging_forecast_view_globe"),
                    output_widget("aging_forecast")),
                col_widths=[6, 6],
                class_="priority-chart-row aging-detail-row",
            ),
            ui.layout_columns(
                _card("Top Elderly Share Ranking",
                    ui.input_slider("aging_year", "Year", 1950, 2023, 2023, step=1, sep=""),
                    output_widget("elderly_ranking")),
                col_widths=[12],
                class_="priority-chart-row ranking-row",
            ),
            class_="page-shell story-page aging-page",
        ),
        value="Aging Societies",
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 4: RAPID GROWTH Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    
    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 5: MIGRATION Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    # ──── TAB 4: RAPID GROWTH ────
    ui.nav_panel("Rapid Growth",
        ui.tags.div(
            ui.tags.h3("High Fertility & Rapid Growth", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Decision lens: "),
                "this story follows high-fertility countries where young populations create momentum for rapid growth, "
                "shaping education, employment, and infrastructure needs.",
                class_="section-note",
            ),
            ui.output_ui("growth_kpis"),
            ui.layout_columns(
                _card("Population Growth Rate",
                    ui.input_selectize("growth_countries", "", choices=COUNTRIES, selected=GROWTH_DEFAULTS, multiple=True),
                    output_widget("growth_lines"),
                ),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Top Children Share Ranking",
                    ui.input_slider("growth_year", "Year", 1950, 2023, 2023, step=1, sep=""),
                    output_widget("children_ranking"),
                ),
                _card("Fertility Rate Forecast",
                    ui.input_selectize("growth_forecast_country", "", choices=COUNTRIES, selected="Nigeria"),
                    output_widget("growth_forecast"),
                ),
                col_widths=[6, 6],
            ),
            class_="page-shell story-page growth-page",
        ),
        value="Rapid Growth",
    ),

    ui.nav_panel("Explore",
        ui.tags.div(
            ui.output_ui("explore_content"),
            class_="page-shell story-page explore-page",
        ),
        value="Explore",
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 6: ML ANALYSIS Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    ui.nav_panel("Similar Futures",
        ui.tags.div(
            ui.tags.h3("Similar Futures: Clustering & Country Peers", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Analytical lens: "),
                "K-Means turns many indicators into a 2D story: countries with similar demographic futures are not always geographic neighbors.",
                class_="section-note",
            ),
            ui.output_ui("ml_kpis"),
            ui.layout_columns(
                _card("PCA: 4 Demographic Clusters",
                    ui.input_checkbox("ml_highlight_war", "Highlight war-torn countries", value=False),
                    output_widget("pca_scatter")),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Similarity Radar",
                    ui.input_selectize("similarity_country", "Compare", choices=COUNTRIES, selected='Japan'),
                    globe_handoff_button("similarity_view_globe"),
                    output_widget("similarity_radar"),
                ),
                _card("Top 10 Most Similar", output_widget("similarity_table")),
                col_widths=[6, 6],
            ),
            class_="page-shell story-page ml-page",
        ),
        value="ML Analysis",
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 7: COUNTRY EXPLORER Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    ui.nav_panel("Country Explorer",
        ui.tags.div(
            ui.tags.h3("Country Explorer", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Use case: "),
                "start with one country, compare peers, then inspect its age structure and a simple forecast for planning-relevant indicators.",
                class_="section-note",
            ),
            ui.tags.div(
                ui.input_selectize("explorer_country", "Search country", choices=COUNTRIES, selected='Vietnam'),
                globe_handoff_button("explorer_view_globe"),
                style="max-width:400px; margin:0 auto 1rem;",
            ),
            ui.output_ui("country_kpis"),
            ui.output_ui("country_insight"),
            ui.layout_columns(
                _card("Demographic Profile",
                    ui.input_selectize("explorer_compare", "Compare with", choices=COUNTRIES, selected=[], multiple=True),
                    output_widget("country_multiline"),
                ),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Age Structure", output_widget("explorer_age_structure")),
                _card("Forecast",
                    ui.input_selectize("explorer_forecast_ind", "", choices=['Median age','Fertility rate','Life expectancy','Population growth rate'], selected='Median age'),
                    output_widget("explorer_forecast"),
                ),
                col_widths=[5, 7],
                class_="priority-chart-row explorer-detail-row",
            ),
            class_="page-shell story-page country-page",
        ),
        value="Country Explorer",
    ),

    # Ă¢â€â‚¬Ă¢â€â‚¬ TAB 8: FORECAST Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    ui.nav_panel("Forecast",
        ui.tags.div(
            ui.tags.h3("Trend Forecast: 2025-2050", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Planning lens: "),
                "simple linear projections from 1950-2023 data let you compare where countries are heading. "
                "Treat these as illustrative trends, not precise predictions.",
                class_="section-note",
            ),
            ui.tags.div(
                ui.input_selectize("forecast_countries", "Countries",
                    choices=COUNTRIES, selected=FORECAST_DEFAULTS, multiple=True),
                ui.input_selectize("forecast_indicator", "Indicator",
                    choices=FORECAST_INDICATORS, selected='Median age'),
                ui.input_slider("forecast_horizon", "Forecast horizon (years from 2025)", 5, 25, 15, step=5),
                ui.input_checkbox("forecast_highlight_war", "Include war-torn countries", value=False),
                class_="control-row",
            ),
            ui.layout_columns(
                _card("Multi-Country Forecast", output_widget("forecast_lines")),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Top / Bottom 12", output_widget("forecast_trend")),
                _card("Forecast Table", output_widget("forecast_values_table")),
                col_widths=[6, 6],
            ),
            class_="page-shell story-page forecast-page",
        ),
        value="Forecast",
    ),
        title="Demographic Stories Explorer",
        id="main_nav",
    ),
)


# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
# SERVER
# Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
def server(input, output, session):

    # Ă¢â€â‚¬Ă¢â€â‚¬ Dark mode sync Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    def _use_dark_theme():
        """Call at start of each render_widget to reactively track dark mode."""
        try:
            dark = bool(input.dark_mode())
        except Exception:
            dark = False
        set_theme_dark(dark)

    @reactive.effect
    @reactive.event(input.dark_mode)
    def _sync_dark_theme():
        set_theme_dark(bool(input.dark_mode()))

    # Ă¢â€â‚¬Ă¢â€â‚¬ Navigation between tabs Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬Ă¢â€â‚¬
    @reactive.effect
    @reactive.event(input.navigate_to)
    def _nav():
        tab = input.navigate_to()
        if tab:
            ui.update_navs("main_nav", selected=tab)

    @lru_cache(maxsize=512)
    def _country_from_iso(iso):
        if not iso:
            return None
        df = load_master_dataset()
        row = df[(df["Code"] == iso.upper()) & df["Entity"].notna()]
        if row.empty:
            return None
        return row["Entity"].iloc[0]

    @lru_cache(maxsize=512)
    def _iso_from_country(country):
        if not country:
            return None
        df = load_master_dataset()
        row = df[(df["Entity"] == country) & df["Code"].notna()]
        if row.empty:
            return None
        return row["Code"].iloc[-1]

    @reactive.effect
    @reactive.event(input.split_country_iso)
    def _split_globe_clicked():
        country = _country_from_iso(input.split_country_iso())
        if country:
            ui.update_selectize("globe_country", selected=country)
            ui.update_selectize("explorer_country", selected=country)
            ui.update_selectize("disruption_country", selected=country)
            ui.update_selectize("similarity_country", selected=country)
            ui.update_selectize("aging_country_pick", selected=country)

    @reactive.effect
    async def _split_update_globe():
        payload = _split_globe_payload(input.globe_year(), input.globe_indicator())
        await session.send_custom_message("split_update_globe_data", {
            "data": payload,
            "indicator": input.globe_indicator(),
        })

    @reactive.effect
    async def _globe_country_to_globe():
        country = input.globe_country()
        iso = _iso_from_country(country)
        if iso:
            await session.send_custom_message("split_select_country", {"iso": iso})
    def _open_globe_country(country, year=2023, indicator="Demographic Cluster"):
        if not country:
            return
        ui.update_selectize("globe_country", selected=country)
        ui.update_slider("globe_year", value=year)
        ui.update_selectize("globe_indicator", selected=indicator)

    @reactive.effect
    @reactive.event(input.aging_pick_view_globe)
    def _aging_pick_to_globe():
        _open_globe_country(input.aging_country_pick(), year=2023, indicator="Median age")

    @reactive.effect
    @reactive.event(input.aging_forecast_view_globe)
    def _aging_forecast_to_globe():
        _open_globe_country(input.aging_forecast_country(), year=2023, indicator="Median age")

    @reactive.effect
    @reactive.event(input.disruption_view_globe)
    def _disruption_to_globe():
        _open_globe_country(input.disruption_country(), year=2023, indicator="Population growth rate")

    @reactive.effect
    @reactive.event(input.similarity_view_globe)
    def _similarity_to_globe():
        _open_globe_country(input.similarity_country(), year=2023, indicator="Demographic Cluster")

    @reactive.effect
    @reactive.event(input.explorer_view_globe)
    def _explorer_to_globe():
        _open_globe_country(input.explorer_country(), year=2023, indicator="Demographic Cluster")

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    # ═══════════════════════════════════════════════════════════
    # STORY CONTROLS — country_group, story button, focus, legend
    # ═══════════════════════════════════════════════════════════
    MIGRATION_ISOS = ["SYR", "YEM", "ARE", "QAT", "KWT", "OMN"]
    FERTILITY_ISOS = ["KOR", "TWN", "HKG", "JPN"]
    STORY_ISOS = {"migration": MIGRATION_ISOS, "fertility": FERTILITY_ISOS}

    story_panel_open = reactive.Value(False)

    @render.ui
    def story_button_ui():
        ind = input.globe_indicator()
        if ind not in ("net_migration_rate", "fertility_rate"):
            return None
        if story_panel_open.get():
            return None  # hide button when story is already open
        label = "See the story" if ind == "net_migration_rate" else "See the story: ultra-low fertility"
        return ui.input_action_button("open_story", label, class_="story-open-btn")

    @reactive.effect
    @reactive.event(input.open_story)
    def _handle_open_story():
        story_panel_open.set(True)
        ui.update_navs("main_nav", selected="Explore")

    @reactive.effect
    @reactive.event(input.close_story)
    def _handle_close_story():
        story_panel_open.set(False)

    @render.ui
    def story_focus_ui():
        ind = input.globe_indicator()
        if ind not in ("net_migration_rate", "fertility_rate"):
            return None
        isos = STORY_ISOS.get(ind == "net_migration_rate" and "migration" or "fertility", [])
        names = [c for c in COUNTRIES if _iso_from_country(c) in isos]
        return ui.input_selectize("story_countries", "Focus countries",
            choices=COUNTRIES, selected=names, multiple=True)

    @render.ui
    def globe_legend_ui():
        ind = input.globe_indicator()
        legends = {
            "net_migration_rate": ("linear-gradient(to right, #f02840, #161c34, #00d2ff)", "Out", "In"),
            "fertility_rate": ("linear-gradient(to right, #f024a0, #8b3ff5, #06c8f0)", "High", "Low"),
            "life_expectancy": ("linear-gradient(to right, #ef4444, #fbbf24, #10d97a)", "Low", "High"),
            "child_mortality": ("linear-gradient(to right, #22c55e, #eab308, #ef4444)", "Low", "High"),
            "death_rate": ("linear-gradient(to right, #22c55e, #eab308, #ef4444)", "Low", "High"),
        }
        grad, lo, hi = legends.get(ind, ("linear-gradient(to right, #666, #ccc)", "Low", "High"))
        return ui.tags.div(
            ui.tags.div(style=f"width:120px; height:7px; border-radius:4px; background:{grad}; margin-bottom:2px; border:1px solid rgba(255,255,255,0.12);"),
            ui.tags.div(
                ui.tags.span(lo),
                ui.tags.span(hi, style="float:right;"),
                style="color:rgba(255,255,255,0.65); font-size:0.52rem; line-height:1; width:120px; font-weight:600; letter-spacing:0.03em;",
            ),
        )

    @reactive.effect
    @reactive.event(input.country_group)
    def _sync_country_group_to_lens():
        grp = input.country_group()
        if grp == "migration":
            ui.update_selectize("globe_indicator", selected="net_migration_rate")
        elif grp == "fertility":
            ui.update_selectize("globe_indicator", selected="fertility_rate")
        # global keeps current lens

    @reactive.effect
    async def _send_focus_group():
        ind = input.globe_indicator()

        if ind == "net_migration_rate":
            focus = {"open": True, "dim": True,
                     "isos": MIGRATION_OUTFLOW + MIGRATION_INFLOW,
                     "origins": MIGRATION_OUTFLOW, "hosts": MIGRATION_INFLOW,
                     "target": {"longitude": 45, "latitude": 22, "zoom": 1.3}}
        elif ind == "fertility_rate":
            focus = {"open": True, "dim": True,
                     "isos": FERTILITY_ISOS,
                     "origins": [], "hosts": [],
                     "target": {"longitude": 128, "latitude": 30, "zoom": 1.4}}
        else:
            focus = {"open": False, "dim": False, "isos": [],
                     "origins": [], "hosts": [],
                     "target": None}

        await session.send_custom_message("focus_group", {
            "open": focus["open"],
            "isos": focus["isos"],
            "origins": focus["origins"],
            "hosts": focus["hosts"],
            "dim": focus["dim"],
            "targetState": focus["target"] or {"longitude": 0, "latitude": 10, "zoom": 0.85},
        })

    # ═══════════════════════════════════════════════════════════
    # EXPLORE TAB — Migration & Fertility story views
    # ═══════════════════════════════════════════════════════════

    @render.ui
    def explore_content():
        ind = input.globe_indicator()
        is_story_lens = ind in ("net_migration_rate", "fertility_rate")
        is_open = story_panel_open.get()

        if is_story_lens and is_open:
            story_id = ind
        else:
            story_id = None

        if story_id == "net_migration_rate":
            return ui.tags.div(
                ui.tags.div(
                    ui.tags.h3("Migration Hotspots", style="margin:0;"),
                    ui.input_action_button("close_story", "✕ Close story", class_="story-close-btn"),
                    style="display:flex; justify-content:space-between; align-items:center; padding:1rem 0 0.5rem;",
                ),
                ui.tags.div(
                    ui.tags.strong("Story: "),
                    "The Gulf and the Levant sit close together but tell opposite migration stories. "
                    "Syria and Yemen show war-linked outflow; the Gulf economies show labor-market inflow.",
                    class_="section-note",
                ),
                ui.layout_columns(
                    _card("Net Migration Over Time", output_widget("migration_story_lines_chart")),
                    _card("Peak Migration Shock", output_widget("migration_peak_shocks_chart")),
                    col_widths=[6, 6],
                ),
            )

        if story_id == "fertility_rate":
            return ui.tags.div(
                ui.tags.div(
                    ui.tags.h3("Ultra-Low Fertility", style="margin:0;"),
                    ui.input_action_button("close_story", "✕ Close story", class_="story-close-btn"),
                    style="display:flex; justify-content:space-between; align-items:center; padding:1rem 0 0.5rem;",
                ),
                ui.tags.div(
                    ui.tags.strong("Story: "),
                    "Replacement fertility is about 2.1 children per woman. South Korea, Taiwan, Hong Kong, and Japan all fall far below that benchmark. "
                    "Hyper-urbanization, extreme living costs, and changing societal expectations drive this unprecedented decline.",
                    class_="section-note",
                ),
                ui.layout_columns(
                    _card("Fertility vs Replacement", output_widget("fertility_replacement_chart")),
                    _card("Lowest Fertility Ranking", output_widget("fertility_lowest_ranking_chart")),
                    col_widths=[6, 6],
                ),
            )

        # Default: no story lens selected
        return ui.tags.div(
            ui.tags.h3("Explore Demographic Stories", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("How to explore: "),
                "Select a Globe Lens with a ★ star in the left panel to unlock story views. "
                "The globe will highlight relevant countries and zoom to the region.",
                class_="section-note",
            ),
            ui.layout_columns(
                _card("World Map", output_widget("world_map")),
                _card("Global Trends 1950-2023", output_widget("explore_global_trends")),
                col_widths=[6, 6],
            ),
        )

    @render_widget
    def migration_story_lines_chart():
        isos = MIGRATION_OUTFLOW + MIGRATION_INFLOW
        return migration_story_lines(isos)

    @render_widget
    def migration_peak_shocks_chart():
        isos = MIGRATION_OUTFLOW + MIGRATION_INFLOW
        return migration_peak_shocks(isos)

    @render_widget
    def fertility_replacement_chart():
        return fertility_replacement_lines(FERTILITY_ISOS)

    @render_widget
    def fertility_lowest_ranking_chart():
        year = input.globe_year()
        return fertility_lowest_ranking(year, FERTILITY_ISOS)

    @render_widget
    def explore_global_trends():
        return global_trend_lines(compact=False)

    # ═══════════════════════════════════════════════════════════
    # DEEP DIVE PANEL — floating overlay on globe when country clicked
    # Adapted from globevis/app.py
    # ═══════════════════════════════════════════════════════════
    import json, os
    _history_db = {}
    _history_path = os.path.join(os.path.dirname(__file__), "globevis", "data", "historical_events.json")
    if os.path.exists(_history_path):
        with open(_history_path, "r", encoding="utf-8") as f:
            _history_db = json.load(f)

    selected_country = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.split_country_iso)
    def _handle_globe_click():
        iso = input.split_country_iso()
        if iso:
            selected_country.set(iso.upper())

    @reactive.effect
    @reactive.event(input.close_deep_dive)
    async def _handle_close_deep_dive():
        selected_country.set(None)
        await session.send_custom_message("panel_closed", {})

    @render.ui
    def deep_dive_panel():
        iso = selected_country.get()
        if not iso:
            return None

        df = load_master_dataset()
        country_df = df[df["Code"] == iso]
        if country_df.empty:
            return None

        country_name = country_df["Entity"].iloc[0]

        return ui.tags.div(
            ui.tags.div(
                ui.tags.div(country_name, class_="deep-dive-title"),
                ui.input_action_button("close_deep_dive", "✕", class_="deep-dive-close"),
                class_="deep-dive-header",
            ),
            ui.tags.div(
                f"Trend for {country_name}. Red line = currently selected year ({input.globe_year()}).",
                class_="deep-dive-content",
            ),
            ui.tags.div(
                output_widget("deep_dive_plot"),
                class_="deep-dive-plot",
            ),
            ui.output_ui("deep_dive_history_text"),
            class_="deep-dive-panel",
        )

    @render.ui
    def deep_dive_history_text():
        iso = selected_country.get()
        if not iso or iso not in _history_db:
            return None

        year = input.globe_year()
        country_history = _history_db[iso]

        current_period = None
        for p in country_history:
            if p["start"] <= year <= p["end"]:
                current_period = p
                break

        if not current_period:
            return None

        return ui.tags.div(
            ui.tags.div(
                ui.tags.span(f"Period {current_period['start']}-{current_period['end']} Context:", class_="history-period-label"),
                ui.tags.span(current_period["period"], class_="history-period-title"),
                class_="history-header-block",
            ),
            ui.tags.p(current_period["details"], class_="history-details"),
            ui.tags.div(
                ui.tags.span(current_period.get("source", ""), class_="history-source"),
                class_="history-footer",
            ),
            class_="vn-history-box",
        )

    # High-performance FigureWidget for deep dive trend chart
    _deep_dive_fig = go.FigureWidget()
    _deep_dive_fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        height=180,
        font=dict(color="#cbd5e1", size=10),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
    )
    _deep_dive_fig.add_scatter(x=[], y=[], mode="lines", line=dict(color="#818cf8", width=2))
    _deep_dive_fig.add_vline(x=2023, line_width=2, line_dash="dash", line_color="#ef4444")

    @render_widget
    def deep_dive_plot():
        return _deep_dive_fig

    @reactive.effect
    def _update_deep_dive_chart():
        iso = selected_country.get()
        if not iso:
            return

        indicator = input.globe_indicator()
        # Map indicator label to data column
        col_map = {
            "Fertility rate": "Fertility rate",
            "Life expectancy": "Life expectancy",
            "Median age": "Median age",
            "Population growth rate": "Population growth rate",
            "Elderly share (%)": "Elderly share (%)",
            "Children share (%)": "Children share (%)",
            "Population": "Population",
        }
        col = col_map.get(indicator, "Population")

        df = load_master_dataset()
        country_df = df[df["Code"] == iso].sort_values("Year")

        with _deep_dive_fig.batch_update():
            _deep_dive_fig.data[0].x = country_df["Year"]
            _deep_dive_fig.data[0].y = country_df[col]
            _deep_dive_fig.layout.title = indicator

    @reactive.effect
    def _update_deep_dive_vline():
        iso = selected_country.get()
        if not iso:
            return
        year = input.globe_year()
        if len(_deep_dive_fig.layout.shapes) > 0:
            with _deep_dive_fig.batch_update():
                _deep_dive_fig.layout.shapes[0].x0 = year
                _deep_dive_fig.layout.shapes[0].x1 = year

    # HOME
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def home_kpis():
        year = input.globe_year()
        df = load_master_dataset()
        world = df[df['Entity'] == 'World']
        w_year = world[world['Year'] == year]
        if w_year.empty:
            return ui.tags.div()
        w = w_year.iloc[0]

        # Build compact KPI cards
        pop_val = f"{w['Population']/1e9:.2f}B" if pd.notna(w.get('Population')) else '-'
        fert_val = f"{w['Fertility rate']:.1f}" if pd.notna(w.get('Fertility rate')) else '-'
        le_val   = f"{w['Life expectancy']:.0f} yrs" if pd.notna(w.get('Life expectancy')) else '-'
        age_val  = f"{w['Median age']:.0f}" if pd.notna(w.get('Median age')) else '-'
        growth_val = f"{w['Population growth rate']:.2f}%" if pd.notna(w.get('Population growth rate')) else '-'

        kpi_data = [
            ("Population", pop_val, "World, selected year"),
            ("Fertility rate", fert_val, "children per woman"),
            ("Life expectancy", le_val, "at birth"),
            ("Median age", age_val, "years"),
            ("Pop. growth rate", growth_val, "annual %"),
        ]
        items = [
            ui.tags.div(
                ui.tags.div(lbl, class_="metric-label"),
                ui.tags.div(num, class_="metric-value"),
                ui.tags.div(note, class_="metric-note"),
                class_="metric-card",
            )
            for lbl, num, note in kpi_data
        ]
        return ui.tags.div(*items, class_="metric-grid")

    # Map globe_indicator keys → DataFrame column names
    INDICATOR_COLUMN = {
        "net_migration_rate": "Net migration rate",
        "fertility_rate": "Fertility rate",
        "life_expectancy": "Life expectancy",
        "child_mortality": "Child mortality rate",
        "death_rate": "Death rate",
    }
    def _indicator_col(key: str) -> str:
        return INDICATOR_COLUMN.get(key, key)

    @render_widget
    def world_map():
        _use_dark_theme()
        return world_map_chart(year=input.globe_year(), indicator=_indicator_col(input.globe_indicator()),
                               compact=True, highlight_war_torn=False)

    @render_widget
    def home_global_trends():
        _use_dark_theme()
        fig = global_trend_lines(compact=True)
        return fig

    @render_widget
    def home_cluster_mix():
        _use_dark_theme()
        year = input.globe_year()
        clusters = run_clustering(year=year)
        order = list(CLUSTER_COLORS.keys())
        counts = clusters['Cluster Label'].value_counts().reindex(order, fill_value=0)

        fig = go.Figure(go.Bar(
            x=counts.values,
            y=counts.index,
            orientation='h',
            marker=dict(color=[CLUSTER_COLORS[label] for label in counts.index]),
            text=counts.values,
            textposition='outside',
            hovertemplate='%{y}<br>%{x} countries<extra></extra>',
        ))
        fig.update_layout(
            title=None,
            height=210,
            margin=dict(l=10, r=38, t=8, b=24),
            xaxis_title='Countries',
            yaxis_title='',
            xaxis=dict(range=[0, max(70, int(counts.max()) + 10)]),
        )
        fig.update_yaxes(autorange='reversed')
        return clean_template(fig)

    @render_widget
    def home_elderly_ranking():
        _use_dark_theme()
        fig = comparison_ranking_bar('Elderly share (%)', year=input.globe_year(), top_n=6, color_scale='Reds')
        fig.update_layout(title=None, height=240, margin=dict(l=10, r=28, t=8, b=26))
        return fig

    @render_widget
    def home_children_ranking():
        _use_dark_theme()
        fig = comparison_ranking_bar('Children share (%)', year=input.globe_year(), top_n=6, color_scale='Greens')
        fig.update_layout(height=210, margin=dict(l=20, r=30, t=40, b=20))
        return fig

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # GLOBAL TRANSITION
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def transition_kpis():
        df = load_master_dataset()
        w = df[df['Entity'] == 'World']
        f50 = w[w['Year']==1950]['Fertility rate'].values[0]
        f23 = w[w['Year']==2023]['Fertility rate'].values[0]
        le50 = w[w['Year']==1950]['Life expectancy'].values[0]
        le23 = w[w['Year']==2023]['Life expectancy'].values[0]
        vals = [
            ("Fertility 1950", f"{f50:.1f}", "#e74c3c"),
            ("Fertility 2023", f"{f23:.1f}", "#e94560"),
            ("Life Expectancy 1950", f"{le50:.0f} yrs", "#2980b9"),
            ("Life Expectancy 2023", f"{le23:.0f} yrs", "#27ae60"),
            ("Improvement", f"+{le23-le50:.0f} yrs", "#8e44ad"),
        ]
        items = [ui.tags.div(ui.tags.div(num, class_="kpi-num", style=f"color:{c}"),
                            ui.tags.div(lbl, class_="kpi-lbl"), class_="kpi-item")
                for lbl, num, c in vals]
        return ui.tags.div(*items, class_="kpi-banner")

    @render_widget
    def bubble_scatter():
        _use_dark_theme()
        return bubble_scatter_year(input.transition_year(),
                                   highlight_war_torn=input.transition_highlight_war())

    @render_widget
    def global_trends():
        _use_dark_theme()
        return global_trend_lines()

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # AGING SOCIETIES
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def aging_kpis():
        df = load_master_dataset()
        cdf = df[(df['Year']==2023) & (df['Entity'].isin(AGING_DEFAULTS))]
        items = []
        for _, r in cdf.iterrows():
            items.append(ui.tags.div(
                ui.tags.div(r['Entity'], class_="compact-kpi-title"),
                ui.tags.div(
                    ui.tags.div(f"Median age: {r['Median age']:.0f}"),
                    ui.tags.div(f"Elderly share: {r['Elderly share (%)']:.1f}%"),
                    ui.tags.div(f"Fertility: {r['Fertility rate']:.1f}"),
                    class_="kpi-stat-lines",
                ),
                class_="compact-kpi-card",
            ))
        return ui.tags.div(*items, class_="compact-kpi-grid")

    @render_widget
    def aging_lines():
        _use_dark_theme()
        countries = list(input.aging_countries()) if input.aging_countries() else AGING_DEFAULTS
        return aging_line_chart(countries)

    @render_widget
    def age_structure():
        _use_dark_theme()
        return age_structure_stacked(input.aging_country_pick())

    @render_widget
    def elderly_ranking():
        _use_dark_theme()
        return elderly_ranking_bar(year=input.aging_year())

    @render_widget
    def aging_forecast():
        _use_dark_theme()
        return country_forecast_chart(input.aging_forecast_country(), 'Median age')

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # RAPID GROWTH
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def growth_kpis():
        df = load_master_dataset()
        cdf = df[(df['Year']==2023) & (df['Entity'].isin(GROWTH_DEFAULTS))]
        items = []
        for _, r in cdf.iterrows():
            items.append(ui.tags.div(
                ui.tags.div(r['Entity'], class_="compact-kpi-title"),
                ui.tags.div(
                    ui.tags.div(f"Pop. growth: {r['Population growth rate']:.2f}%", style="color:#159947;"),
                    ui.tags.div(f"Children share: {r['Children share (%)']:.0f}%", style="color:#159947;"),
                    ui.tags.div(f"Fertility: {r['Fertility rate']:.1f}", style="color:#159947;"),
                    class_="kpi-stat-lines",
                ),
                class_="compact-kpi-card",
            ))
        return ui.tags.div(*items, class_="compact-kpi-grid")

    @render_widget
    def growth_lines():
        _use_dark_theme()
        countries = list(input.growth_countries()) if input.growth_countries() else GROWTH_DEFAULTS
        return growth_line_chart(countries)

    @render_widget
    def children_ranking():
        _use_dark_theme()
        return children_share_bar(year=input.growth_year())

    @render_widget
    def growth_forecast():
        _use_dark_theme()
        return country_forecast_chart(input.growth_forecast_country(), 'Fertility rate')

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # MIGRATION
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def migration_kpis():
        df = load_master_dataset()
        indicator = 'Total number of international immigrants'
        cdf = (
            df[df['Entity'].isin(MIGRATION_DEFAULTS)]
            .dropna(subset=[indicator])
            .sort_values(['Entity', 'Year'])
            .groupby('Entity', as_index=False)
            .tail(1)
        )
        items = []
        for _, r in cdf.iterrows():
            ms = r.get(indicator, 0)
            v = f"{ms/1e6:.2f}M in {int(r['Year'])}" if not pd.isna(ms) else "No data"
            items.append(ui.tags.div(
                ui.tags.div(r['Entity'], class_="kpi-lbl", style="font-weight:600; color:#333;"),
                ui.tags.div(v, class_="kpi-num", style="font-size:1.1rem; color:#f39c12;"),
                class_="kpi-item",
            ))
        return ui.tags.div(*items, class_="kpi-banner")

    @render_widget
    def migration_demographic_position():
        _use_dark_theme()
        fig = bubble_scatter_year(2023, highlight_war_torn=True)
        fig.update_layout(height=480)
        return fig

    @render_widget
    def migration_trends():
        _use_dark_theme()
        countries = list(input.migration_countries()) if input.migration_countries() else MIGRATION_DEFAULTS
        return migration_trend_chart(countries, highlight_war_torn=input.migration_highlight_war())

    @render_widget
    def disruption_dashboard():
        _use_dark_theme()
        return disruption_dashboard_chart(input.disruption_country())

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # ML ANALYSIS
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def ml_kpis():
        clusters = run_clustering()
        counts = clusters['Cluster Label'].value_counts()
        color_map = {
            'Aging low-fertility societies': '#e74c3c',
            'Young high-fertility populations': '#27ae60',
            'Growing transitional countries': '#f39c12',
            'Slow-growth transitional countries': '#2980b9',
        }
        items = []
        for lbl, cnt in counts.items():
            items.append(ui.tags.div(
                ui.tags.div(f"{cnt}", class_="kpi-num", style=f"color:{color_map.get(lbl,'#888')};"),
                ui.tags.div(lbl, class_="kpi-lbl"),
                class_="kpi-item",
            ))
        return ui.tags.div(*items, class_="kpi-banner")

    @render_widget
    def pca_scatter():
        _use_dark_theme()
        return cluster_pca_scatter(highlight_war_torn=input.ml_highlight_war())

    @render_widget
    def similarity_radar():
        _use_dark_theme()
        return similar_countries_radar(input.similarity_country())

    @render_widget
    def similarity_table():
        _use_dark_theme()
        country = input.similarity_country()
        similar = get_similar_countries(country, top_n=10)
        if similar.empty:
            fig = go.Figure().add_annotation(text='No data', x=0.5, y=0.5, showarrow=False)
            return clean_template(fig)
        fig = go.Figure(data=[go.Table(
            header=dict(values=['#', 'Country', 'Similarity'], fill_color='#f8f9fa',
                       font=dict(color='#333', size=12), align='left', line_color='#ddd'),
            cells=dict(
                values=[list(range(1,len(similar)+1)), similar['Entity'].tolist(),
                       [f'{s:.3f}' for s in similar['Similarity']]],
                fill_color='white', font=dict(color='#333', size=11),
                align='left', height=28, line_color='#eee',
            ),
        )])
        fig.update_layout(title=f'Top 10 Most Similar to {country}', height=400, margin=dict(l=0,r=0,t=40,b=0))
        return clean_template(fig)

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # SPLIT VIEW
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def globe_overlay_badge():
        country = input.globe_country()
        year = input.globe_year()
        warning = ui.tags.span("Conflict", class_="globe-overlay-warning") if country in WAR_TORN else None
        return ui.tags.div(
            ui.tags.span(country, class_="globe-overlay-country"),
            ui.tags.span(f"{year} · {input.globe_indicator()}", class_="globe-overlay-meta"),
            warning,
            class_="globe-overlay-chip",
        )

    @render.ui
    def globe_country_badge():
        country = input.globe_country()
        year = input.globe_year()
        badge = ui.tags.span("Conflict-affected", class_="split-badge") if country in WAR_TORN else None
        return ui.tags.div(
            ui.tags.div(
                ui.tags.div(country, class_="split-selected-name"),
                ui.tags.div(f"{year} snapshot. Globe color: {input.globe_indicator()}", class_="split-selected-meta"),
            ),
            badge,
            class_="split-selected-band",
        )

    @render.ui
    def split_kpis():
        country = input.globe_country()
        year = input.globe_year()
        df = load_master_dataset()
        row = df[(df["Entity"] == country) & (df["Year"] == year)]
        if row.empty:
            return ui.tags.div()
        r = row.iloc[0]
        vals = [
            ("Population", f"{r['Population']/1e6:.1f}M" if pd.notna(r.get("Population")) else "-", "selected year"),
            ("Fertility", f"{r['Fertility rate']:.1f}" if pd.notna(r.get("Fertility rate")) else "-", "children/woman"),
            ("Life Exp.", f"{r['Life expectancy']:.0f} yrs" if pd.notna(r.get("Life expectancy")) else "-", "at birth"),
            ("Median Age", f"{r['Median age']:.0f}" if pd.notna(r.get("Median age")) else "-", "years"),
            ("Growth", f"{r['Population growth rate']:.2f}%" if pd.notna(r.get("Population growth rate")) else "-", "annual"),
        ]
        return ui.tags.div(
            *[
                ui.tags.div(
                    ui.tags.div(lbl, class_="metric-label"),
                    ui.tags.div(num, class_="metric-value"),
                    ui.tags.div(note, class_="metric-note"),
                    class_="metric-card",
                )
                for lbl, num, note in vals
            ],
            class_="metric-grid",
        )

    @render_widget
    def globe_country_multiline():
        _use_dark_theme()
        return country_multi_line(input.globe_country(), compare_countries=["World"])

    @render_widget
    def split_age_structure():
        _use_dark_theme()
        return age_structure_stacked(input.globe_country())

    @render_widget
    def split_forecast():
        _use_dark_theme()
        return country_forecast_chart(input.globe_country(), "Median age")

    # COUNTRY EXPLORER
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @render.ui
    def country_kpis():
        country = input.explorer_country()
        profile = get_demographic_profile(country)
        if 'error' in profile:
            return ui.tags.p(f"No data for {country}")
        vals = [
            ("Population", profile.get('Population','-'), "#1e3a5f"),
            ("Fertility", profile.get('Fertility rate','-'), "#e74c3c"),
            ("Life Expectancy", profile.get('Life expectancy','-'), "#27ae60"),
            ("Median Age", profile.get('Median age','-'), "#2980b9"),
            ("Pop Growth", profile.get('Population growth rate','-'), "#f39c12"),
            ("Elderly Share", profile.get('Elderly share (%)','-'), "#e74c3c"),
            ("Children Share", profile.get('Children share (%)','-'), "#27ae60"),
            ("Cluster", profile.get('Cluster','-'), "#8e44ad"),
        ]
        is_war = country in WAR_TORN
        items = []
        if is_war:
            items.append(ui.tags.div(
                ui.tags.span("Conflict-affected", style="font-weight:700; color:#e74c3c; font-size:0.78rem;"),
                style="text-align:center; margin-bottom:0.35rem;",
            ))
        for lbl, num, c in vals:
            if lbl == "Cluster":
                num_node = ui.tags.div(num, class_="cluster-pill")
            else:
                num_node = ui.tags.div(num, class_="kpi-num", style=f"color:{c}")
            items.append(ui.tags.div(num_node, ui.tags.div(lbl, class_="kpi-lbl"), class_="kpi-item"))
        return ui.tags.div(*items, class_="kpi-banner")

    @render.ui
    def country_insight():
        insight = generate_country_insight(input.explorer_country()).replace("**", "")
        return ui.tags.div(
            ui.tags.strong("Auto insight: "),
            insight,
            class_="section-note",
        )

    @render_widget
    def country_multiline():
        _use_dark_theme()
        compare = list(input.explorer_compare()) if input.explorer_compare() else None
        return country_multi_line(input.explorer_country(), compare)

    @render_widget
    def explorer_age_structure():
        _use_dark_theme()
        return age_structure_stacked(input.explorer_country())

    @render_widget
    def explorer_forecast():
        _use_dark_theme()
        return country_forecast_chart(input.explorer_country(), input.explorer_forecast_ind())

    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â
    # FORECAST
    # Ă¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢ÂĂ¢â€¢Â

    @reactive.calc
    def _forecast_countries():
        countries = list(input.forecast_countries()) if input.forecast_countries() else FORECAST_DEFAULTS
        if input.forecast_highlight_war():
            countries = list(set(countries) | set(WAR_TORN))
        return countries

    @render_widget
    def forecast_lines():
        _use_dark_theme()
        return forecast_multi_country(
            _forecast_countries(),
            indicator=input.forecast_indicator(),
            forecast_years=input.forecast_horizon(),
        )

    @render_widget
    def forecast_trend():
        _use_dark_theme()
        order = input.forecast_indicator() in ('Fertility rate', 'Population growth rate')
        return forecast_trend_bar(
            indicator=input.forecast_indicator(),
            top_n=12,
            forecast_years=input.forecast_horizon(),
            ascending=order,
        )

    @render_widget
    def forecast_values_table():
        _use_dark_theme()
        horizon = input.forecast_horizon()
        step = max(5, horizon // 3)
        targets = list(range(2025 + step, 2025 + horizon + 1, step))
        return forecast_table(
            _forecast_countries(),
            indicator=input.forecast_indicator(),
            forecast_years=horizon,
            target_years=targets,
        )


_HERE = Path(__file__).parent
app = App(app_ui, server, static_assets=str(_HERE / "www"))

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://127.0.0.1:{port}")
    app.run(port=port, launch_browser=True)
