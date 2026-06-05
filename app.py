"""
Demographic Stories Explorer — Python Shiny Dashboard
Run: python app.py  or  shiny run app.py --port 8000
"""
from pathlib import Path
import pandas as pd
import numpy as np
from shiny import App, ui, reactive, render
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
)

# ── Globals ──────────────────────────────────────────────────────────
COUNTRIES = get_country_list()
AGING_DEFAULTS = ['Japan', 'South Korea', 'Italy', 'Germany', 'China']
GROWTH_DEFAULTS = ['Nigeria', 'Ethiopia', 'Tanzania', 'Pakistan', 'Democratic Republic of Congo']
MIGRATION_DEFAULTS = ['Ukraine', 'Syria', 'Afghanistan', 'Yemen']
FORECAST_DEFAULTS = ['Vietnam', 'Japan', 'Nigeria', 'Germany', 'India', 'Brazil']
FORECAST_INDICATORS = ['Median age', 'Fertility rate', 'Life expectancy', 'Population growth rate']

# War-torn / conflict-affected highlights — 4 flagship countries for demographic storytelling
# Each represents a distinct region & conflict type with clear demographic disruption visible in data
WAR_TORN = [
    'Ukraine',      # Europe — active war, mass displacement, population crash
    'Syria',        # Middle East — protracted civil war, refugee crisis, migrant stock spike
    'Afghanistan',  # Central Asia — decades of conflict, stuck at high fertility + low life expectancy
    'Yemen',        # Arabian Peninsula — active conflict, humanitarian crisis, demographic reversal
]


# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════
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
    display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr));
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

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f0f0f0; }
::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

/* ── Dark mode toggle ───────────────────────────────── */
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

/* ── Dark theme overrides ───────────────────────────── */
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
"""


# ── Helper functions ─────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════
app_ui = ui.page_navbar(
    ui.head_content(
        ui.tags.style(custom_css),
        ui.include_css("www/custom.css"),
        ui.include_js("www/dashboard.js"),
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

    # ── TAB 1: HOME ──────────────────────────────────────────────────
    ui.nav_panel("Overview",
        ui.layout_sidebar(
            ui.sidebar(
                ui.tags.h5("Filters", style="margin-top:0;"),
                ui.input_slider("year_slider", "Year", 1950, 2023, 2023, step=1, sep=""),
                ui.input_selectize("indicator_sel", "Map color",
                    choices=['Demographic Cluster', 'Population', 'Fertility rate',
                             'Life expectancy', 'Median age', 'Population growth rate',
                             'Elderly share (%)', 'Children share (%)'],
                    selected='Demographic Cluster'),
                ui.hr(),
                ui.input_checkbox("highlight_war", "🔴 Highlight war-torn countries", value=False),
                width=280,
            ),
            ui.tags.div(
                ui.tags.button(
                    ui.tags.span("☀️", class_="icon-slot"),
                    ui.tags.span("Theme"),
                    class_="theme-toggle",
                    onclick="window._toggleDarkMode(); this.querySelector('.icon-slot').textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';",
                ),
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
                        _card("Global Trends 1950–2023", output_widget("home_global_trends")),
                        _card("Cluster Mix", output_widget("home_cluster_mix")),
                        class_="chart-right-stack",
                    ),
                    class_="chart-grid-main",
                ),
                class_="page-shell home-shell",
            ),
        ),
        value="Home",
    ),

    # ── TAB 2: GLOBAL TRANSITION ─────────────────────────────────────
    
    # ── TAB 3: AGING SOCIETIES ───────────────────────────────────────
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
                _card("Age Structure", ui.input_selectize("aging_country_pick", "", choices=COUNTRIES, selected='Japan'), output_widget("age_structure")),
                _card("Median Age Forecast", ui.input_selectize("aging_forecast_country", "", choices=COUNTRIES, selected='Japan'), output_widget("aging_forecast")),
                _card("Top Elderly Share Ranking",
                    ui.input_slider("aging_year", "Year", 1950, 2023, 2023, step=1, sep=""),
                    output_widget("elderly_ranking")),
                col_widths=[4, 4, 4],
            ),
            class_="page-shell story-page aging-page",
        ),
        value="Aging Societies",
    ),

    # ── TAB 4: RAPID GROWTH ──────────────────────────────────────────
    
    # ── TAB 5: MIGRATION ─────────────────────────────────────────────
    ui.nav_panel("War & Disruption",
        ui.tags.div(
            ui.tags.h3("War-Torn Demographic Disruption", style="text-align:center; padding:1rem 0 0.5rem;"),
            ui.tags.div(
                ui.tags.strong("Decision lens: "),
                "conflict shocks can bend otherwise smooth demographic trends, so this page keeps the evidence focused on migrant stock, population growth, mortality, and longevity.",
                class_="section-note",
            ),
            ui.output_ui("migration_kpis"),
            ui.layout_columns(
                _card("2D Demographic Position — War-Torn Countries",
                    output_widget("migration_demographic_position"),
                ),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("International Migrant Stock",
                    ui.input_selectize("migration_countries", "", choices=COUNTRIES, selected=MIGRATION_DEFAULTS, multiple=True),
                    ui.input_checkbox("migration_highlight_war", "🔴 Show all war-torn countries", value=False),
                    output_widget("migration_trends"),
                ),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Disruption Dashboard",
                    ui.input_selectize("disruption_country", "", choices=COUNTRIES, selected='Ukraine'),
                    output_widget("disruption_dashboard"),
                ),
                col_widths=[12],
            ),
            class_="page-shell story-page migration-page",
        ),
        value="Migration",
    ),

    # ── TAB 6: ML ANALYSIS ───────────────────────────────────────────
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
                    ui.input_checkbox("ml_highlight_war", "🔴 Highlight war-torn countries", value=False),
                    output_widget("pca_scatter")),
                col_widths=[12],
            ),
            ui.layout_columns(
                _card("Similarity Radar",
                    ui.input_selectize("similarity_country", "Compare", choices=COUNTRIES, selected='Japan'),
                    output_widget("similarity_radar"),
                ),
                _card("Top 10 Most Similar", output_widget("similarity_table")),
                col_widths=[6, 6],
            ),
            class_="page-shell story-page ml-page",
        ),
        value="ML Analysis",
    ),

    # ── TAB 7: COUNTRY EXPLORER ──────────────────────────────────────
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
                col_widths=[6, 6],
            ),
            class_="page-shell story-page country-page",
        ),
        value="Country Explorer",
    ),

    # ── TAB 8: FORECAST ────────────────────────────────────────────
    
    id="main_nav",
    title="Demographic Stories Explorer",
)


# ══════════════════════════════════════════════════════════════════════
# SERVER
# ══════════════════════════════════════════════════════════════════════
def server(input, output, session):

    # ── Dark mode sync ──────────────────────────────────────────────
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

    # ── Navigation between tabs ──────────────────────────────────────
    @reactive.effect
    @reactive.event(input.navigate_to)
    def _nav():
        tab = input.navigate_to()
        if tab:
            ui.update_navs("main_nav", selected=tab)

    # ═══════════════════════════════════════════════════════════════
    # HOME
    # ═══════════════════════════════════════════════════════════════

    @render.ui
    def home_kpis():
        year = input.year_slider()
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

    @render_widget
    def world_map():
        _use_dark_theme()
        return world_map_chart(year=input.year_slider(), indicator=input.indicator_sel(),
                               compact=True, highlight_war_torn=input.highlight_war())

    @render_widget
    def home_global_trends():
        _use_dark_theme()
        fig = global_trend_lines(compact=True)
        return fig

    @render_widget
    def home_cluster_mix():
        _use_dark_theme()
        year = input.year_slider()
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
        fig = comparison_ranking_bar('Elderly share (%)', year=input.year_slider(), top_n=6, color_scale='Reds')
        fig.update_layout(title=None, height=240, margin=dict(l=10, r=28, t=8, b=26))
        return fig

    @render_widget
    def home_children_ranking():
        _use_dark_theme()
        fig = comparison_ranking_bar('Children share (%)', year=input.year_slider(), top_n=6, color_scale='Greens')
        fig.update_layout(height=210, margin=dict(l=20, r=30, t=40, b=20))
        return fig

    # ═══════════════════════════════════════════════════════════════
    # GLOBAL TRANSITION
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # AGING SOCIETIES
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # RAPID GROWTH
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # MIGRATION
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # ML ANALYSIS
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # COUNTRY EXPLORER
    # ═══════════════════════════════════════════════════════════════

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
                ui.tags.span("⚠️ Conflict-affected", style="font-weight:700; color:#e74c3c; font-size:0.78rem;"),
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

    # ═══════════════════════════════════════════════════════════════
    # FORECAST
    # ═══════════════════════════════════════════════════════════════

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
    print(f"🚀 http://127.0.0.1:{port}")
    app.run(port=port, launch_browser=True)
