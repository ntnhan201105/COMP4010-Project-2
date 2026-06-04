"""
Charts module — Plotly-based visualization functions for the dashboard.
Each function returns a plotly Figure object ready for rendering.
"""
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from .data_loader import load_master_dataset, get_country_list
from .ml_clustering import run_clustering, forecast_indicator

# ── Color palette ───────────────────────────────────────────────────
CLUSTER_COLORS = {
    'Aging low-fertility societies':      '#e74c3c',  # red
    'Young high-fertility populations':   '#2ecc71',  # green
    'Growing transitional countries':     '#f39c12',  # orange
    'Slow-growth transitional countries': '#3498db',  # blue
}

# War-torn / conflict-affected highlights — 4 flagship countries for demographic storytelling
WAR_TORN = [
    'Ukraine',      # Europe — active war, mass displacement, population crash
    'Syria',        # Middle East — protracted civil war, refugee crisis, migrant stock spike
    'Afghanistan',  # Central Asia — decades of conflict, stuck at high fertility + low life expectancy
    'Yemen',        # Arabian Peninsula — active conflict, humanitarian crisis, demographic reversal
]

CLEAN_BG = '#ffffff'
PLOT_BG = '#fafafa'
PAPER_BG = '#ffffff'
FONT_COLOR = '#333333'
GRID_COLOR = '#e5e5e5'

# Dark mode state — set by server before rendering each chart
_theme_dark = False


def set_theme_dark(dark: bool):
    """Set chart theme mode. Call before rendering charts from the server."""
    global _theme_dark
    _theme_dark = dark


def clean_template(fig: go.Figure) -> go.Figure:
    """Apply consistent theme to a figure (light or dark)."""
    if _theme_dark:
        fig.update_layout(
            plot_bgcolor='#1e2130',
            paper_bgcolor='#1e2130',
            font=dict(color='#d5d7e0', size=12, family='Inter, sans-serif'),
            title=dict(font=dict(size=16, color='#e8eaef')),
            xaxis=dict(gridcolor='#2e3342', zeroline=False, linecolor='#3a3f52'),
            yaxis=dict(gridcolor='#2e3342', zeroline=False, linecolor='#3a3f52'),
            legend=dict(font=dict(color='#d5d7e0')),
            margin=dict(l=20, r=20, t=50, b=20),
        )
    else:
        fig.update_layout(
            plot_bgcolor=PLOT_BG,
            paper_bgcolor=PAPER_BG,
            font=dict(color=FONT_COLOR, size=12, family='Inter, sans-serif'),
            title=dict(font=dict(size=16, color='#222')),
            xaxis=dict(gridcolor=GRID_COLOR, zeroline=False, linecolor='#ccc'),
            yaxis=dict(gridcolor=GRID_COLOR, zeroline=False, linecolor='#ccc'),
            legend=dict(font=dict(color=FONT_COLOR)),
            margin=dict(l=20, r=20, t=50, b=20),
        )
    return fig


# ══════════════════════════════════════════════════════════════════════
# OVERVIEW PAGE CHARTS
# ══════════════════════════════════════════════════════════════════════

def world_map_chart(year: int = 2023, indicator: str = 'Population', compact: bool = False,
                    highlight_war_torn: bool = False) -> go.Figure:
    """Choropleth world map colored by demographic cluster or indicator."""
    df = load_master_dataset()
    clusters = run_clustering(year=year)

    df_year = df[(df['Year'] == year)].merge(
        clusters[['Entity', 'Cluster Label']], on='Entity', how='left'
    )

    if indicator in ('Demographic Cluster', 'Cluster Label'):
        color_col = 'Cluster Label'
        color_map = CLUSTER_COLORS
        fig = px.choropleth(
            df_year.dropna(subset=[color_col]),
            locations='Code',
            color=color_col,
            color_discrete_map=color_map,
            hover_name='Entity',
            hover_data={
                'Population': ':,',
                'Median age': ':.1f',
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                'Code': False,
            },
            title=f'Demographic Clusters — {year}',
            category_orders={color_col: list(CLUSTER_COLORS.keys())},
        )
    else:
        fig = px.choropleth(
            df_year,
            locations='Code',
            color=indicator,
            hover_name='Entity',
            hover_data={
                'Population': ':,',
                'Median age': ':.1f',
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                indicator: ':.2f',
                'Code': False,
            },
            title=f'{indicator} — {year}',
            color_continuous_scale='Viridis',
        )

    # Highlight war-torn countries with scatter markers
    if highlight_war_torn:
        war_df = df_year[df_year['Entity'].isin(WAR_TORN)]
        if not war_df.empty:
            fig.add_trace(go.Scattergeo(
                locations=war_df['Code'],
                locationmode='ISO-3',
                text=war_df['Entity'],
                mode='markers+text',
                marker=dict(size=8, color='rgba(255,50,50,0.85)', line=dict(color='white', width=1)),
                textfont=dict(size=8, color='#8B0000', family='Inter, sans-serif'),
                textposition='top center',
                name='War-torn',
                hoverinfo='text',
                showlegend=True,
            ))

    if _theme_dark:
        geo_land = '#252836'
        geo_ocean = '#1a1d27'
        geo_coast = 'rgba(120,140,160,0.4)'
        geo_country = 'rgba(120,140,160,0.3)'
        legend_bg = 'rgba(30,33,48,0.82)'
    else:
        geo_land = '#eef2f6'
        geo_ocean = '#f8fbfd'
        geo_coast = 'rgba(80,96,115,0.35)'
        geo_country = 'rgba(80,96,115,0.25)'
        legend_bg = 'rgba(255,255,255,0.72)'

    fig.update_geos(
        projection_type='equirectangular',
        showcoastlines=True, coastlinecolor=geo_coast,
        showland=True, landcolor=geo_land,
        showocean=True, oceancolor=geo_ocean,
        showcountries=True, countrycolor=geo_country,
        showframe=False,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10 if compact else 35, b=0),
        height=330 if compact else 340,
        legend=dict(font=dict(size=9 if compact else 11),
                   x=0.01, y=0.02, xanchor='left', yanchor='bottom',
                   bgcolor=legend_bg),
    )
    fig = clean_template(fig)
    if compact:
        fig.update_layout(
            title=None,
            margin=dict(l=0, r=0, t=4, b=0),
            height=330,
            legend=dict(font=dict(size=9),
                       x=0.01, y=0.02, xanchor='left', yanchor='bottom',
                       bgcolor='rgba(255,255,255,0.72)'),
        )
    return fig


def animated_world_map_chart(indicator: str = 'Demographic Cluster') -> go.Figure:
    """Client-side animated choropleth by year to avoid Shiny re-render flicker."""
    df = load_master_dataset()
    years = list(range(1950, 2024, 2))
    if 2023 not in years:
        years.append(2023)

    frames = []
    if indicator in ('Demographic Cluster', 'Cluster Label'):
        for year in years:
            clusters = run_clustering(year=year)
            df_year = df[df['Year'] == year].merge(
                clusters[['Entity', 'Cluster Label']], on='Entity', how='left'
            )
            frames.append(df_year.dropna(subset=['Cluster Label']).assign(Year=year))

        plot_df = pd.concat(frames, ignore_index=True)
        fig = px.choropleth(
            plot_df,
            locations='Code',
            color='Cluster Label',
            animation_frame='Year',
            color_discrete_map=CLUSTER_COLORS,
            category_orders={'Cluster Label': list(CLUSTER_COLORS.keys())},
            hover_name='Entity',
            hover_data={
                'Population': ':,',
                'Median age': ':.1f',
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                'Code': False,
                'Year': False,
            },
            title='Demographic clusters over time',
        )
    else:
        plot_df = df[df['Year'].isin(years)].dropna(subset=[indicator]).copy()
        fig = px.choropleth(
            plot_df,
            locations='Code',
            color=indicator,
            animation_frame='Year',
            color_continuous_scale='Viridis',
            range_color=(plot_df[indicator].min(), plot_df[indicator].max()),
            hover_name='Entity',
            hover_data={
                'Population': ':,',
                'Median age': ':.1f',
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                indicator: ':.2f',
                'Code': False,
                'Year': False,
            },
            title=f'{indicator} over time',
        )

    fig.update_geos(
        projection_type='equirectangular',
        showcoastlines=True, coastlinecolor='rgba(80,96,115,0.35)',
        showland=True, landcolor='#eef2f6',
        showocean=True, oceancolor='#f8fbfd',
        showcountries=True, countrycolor='rgba(80,96,115,0.25)',
        showframe=False,
    )
    fig.update_layout(
        height=510,
        margin=dict(l=0, r=0, t=45, b=0),
        updatemenus=[{
            'type': 'buttons',
            'direction': 'left',
            'x': 0.02,
            'y': -0.02,
            'buttons': [
                {
                    'label': 'Play',
                    'method': 'animate',
                    'args': [None, {
                        'frame': {'duration': 700, 'redraw': True},
                        'transition': {'duration': 180},
                        'fromcurrent': True,
                    }],
                },
                {
                    'label': 'Pause',
                    'method': 'animate',
                    'args': [[None], {
                        'frame': {'duration': 0, 'redraw': False},
                        'transition': {'duration': 0},
                    }],
                },
            ],
        }],
    )
    return clean_template(fig)


def animated_cluster_mix_chart() -> go.Figure:
    """Client-side animated cluster composition bar chart by year."""
    years = list(range(1950, 2024, 2))
    if 2023 not in years:
        years.append(2023)

    rows = []
    order = list(CLUSTER_COLORS.keys())
    for year in years:
        clusters = run_clustering(year=year)
        counts = clusters['Cluster Label'].value_counts().reindex(order, fill_value=0)
        for label, count in counts.items():
            rows.append({'Year': year, 'Cluster Label': label, 'Countries': int(count)})

    plot_df = pd.DataFrame(rows)
    fig = px.bar(
        plot_df,
        x='Countries',
        y='Cluster Label',
        color='Cluster Label',
        animation_frame='Year',
        orientation='h',
        color_discrete_map=CLUSTER_COLORS,
        category_orders={'Cluster Label': order},
        range_x=(0, max(70, int(plot_df['Countries'].max()) + 10)),
        text='Countries',
        title='Cluster mix over time',
    )
    fig.update_traces(textposition='outside', hovertemplate='%{y}<br>%{x} countries<extra></extra>')
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=36, t=45, b=20),
        showlegend=False,
        updatemenus=[{
            'type': 'buttons',
            'direction': 'left',
            'x': 0.02,
            'y': -0.15,
            'buttons': [
                {
                    'label': 'Play',
                    'method': 'animate',
                    'args': [None, {
                        'frame': {'duration': 700, 'redraw': True},
                        'transition': {'duration': 180},
                        'fromcurrent': True,
                    }],
                },
                {
                    'label': 'Pause',
                    'method': 'animate',
                    'args': [[None], {
                        'frame': {'duration': 0, 'redraw': False},
                        'transition': {'duration': 0},
                    }],
                },
            ],
        }],
    )
    fig.update_yaxes(autorange='reversed', title='')
    fig.update_xaxes(title='Countries')
    return clean_template(fig)


def finding_cards_data(year: int = 2023) -> list[dict]:
    """Generate finding-card summaries for the overview page."""
    df = load_master_dataset()
    clusters = run_clustering()

    # Merge clusters
    df_year = df[df['Year'] == year].merge(
        clusters[['Entity', 'Cluster Label']], on='Entity', how='inner'
    )

    findings = []

    # Finding 1: Global trend
    old_fert = df[(df['Year'] == 1950) & (df['Entity'] == 'World')]['Fertility rate'].values
    new_fert = df[(df['Year'] == 2023) & (df['Entity'] == 'World')]['Fertility rate'].values
    old_le = df[(df['Year'] == 1950) & (df['Entity'] == 'World')]['Life expectancy'].values
    new_le = df[(df['Year'] == 2023) & (df['Entity'] == 'World')]['Life expectancy'].values

    findings.append({
        'id': 'global_transition',
        'title': 'The world is moving toward lower fertility & longer life',
        'subtitle': f'Fertility: {old_fert[0]:.1f} → {new_fert[0]:.1f} children/woman | '
                    f'Life expectancy: {old_le[0]:.0f} → {new_le[0]:.0f} years',
        'icon': '🌍',
    })

    # Finding 2: Aging
    aging = df_year[df_year['Cluster Label'] == 'Aging low-fertility societies']
    findings.append({
        'id': 'aging',
        'title': 'East Asia & Europe are becoming aging societies',
        'subtitle': f'{len(aging)} countries with low fertility, high median age, rising elderly share',
        'icon': '👴',
    })

    # Finding 3: Young growth
    young = df_year[df_year['Cluster Label'] == 'Young high-fertility populations']
    findings.append({
        'id': 'growth',
        'title': 'African & some Asian countries remain young & fast-growing',
        'subtitle': f'{len(young)} countries with high fertility, young age structure',
        'icon': '👶',
    })

    # Finding 4: Migration-sensitive
    migration_countries = ['Ukraine', 'Syria', 'Venezuela', 'Afghanistan']
    findings.append({
        'id': 'migration',
        'title': 'Some countries show migration-sensitive demographic patterns',
        'subtitle': f'Countries like {", ".join(migration_countries)} show disruption-sensitive patterns',
        'icon': '🔄',
    })

    # Finding 5: Similarity
    findings.append({
        'id': 'similarity',
        'title': 'Similar demographic futures are not always geographic neighbors',
        'subtitle': 'K-Means clustering reveals 4 demographic groups across regions',
        'icon': '🔗',
    })

    return findings


# ══════════════════════════════════════════════════════════════════════
# FINDING 1: GLOBAL DEMOGRAPHIC TRANSITION
# ══════════════════════════════════════════════════════════════════════

def animated_bubble_scatter(
    year_range: tuple = (1950, 2023),
    selected_countries: list = None,
    frame_step: int = 3,
) -> go.Figure:
    """Animated bubble scatter: fertility vs life expectancy, sized by population."""
    df = load_master_dataset()
    clusters = run_clustering()

    df_range = df[(df['Year'] >= year_range[0]) & (df['Year'] <= year_range[1])]

    # Keep only countries with ISO codes
    has_code = df_range['Code'].notna()
    df_range = df_range[has_code].copy()
    df_range = df_range[
        ~df_range['Code'].str.startswith('OWID')
        & (df_range['Code'].str.len() == 3)
    ]

    # Merge cluster info
    df_range = df_range.merge(clusters[['Entity', 'Cluster Label']], on='Entity', how='left')

    # Drop rows missing key data
    df_plot = df_range.dropna(subset=['Fertility rate', 'Life expectancy', 'Population'])

    if selected_countries:
        df_plot = df_plot[df_plot['Entity'].isin(selected_countries)]

    years = sorted(df_plot['Year'].dropna().unique())
    keep_years = {year for year in years if (year - year_range[0]) % frame_step == 0}
    keep_years.add(max(years))
    df_plot = df_plot[df_plot['Year'].isin(keep_years)].sort_values(['Year', 'Entity']).copy()

    years = sorted(keep_years)
    cluster_order = [label for label in CLUSTER_COLORS if label in df_plot['Cluster Label'].dropna().unique()]
    max_pop = df_plot['Population'].max()

    def marker_size(population: pd.Series) -> pd.Series:
        return 5 + (np.sqrt(population) / np.sqrt(max_pop)) * 55

    def make_trace(year: int, cluster_label: str) -> go.Scatter:
        year_cluster = df_plot[
            (df_plot['Year'] == year)
            & (df_plot['Cluster Label'] == cluster_label)
        ]
        return go.Scatter(
            x=year_cluster['Fertility rate'],
            y=year_cluster['Life expectancy'],
            mode='markers',
            name=cluster_label,
            legendgroup=cluster_label,
            marker=dict(
                size=marker_size(year_cluster['Population']) if not year_cluster.empty else [],
                color=CLUSTER_COLORS[cluster_label],
                opacity=0.78,
                line=dict(width=0.5, color='white'),
            ),
            customdata=np.stack(
                [
                    year_cluster['Entity'],
                    year_cluster['Population'],
                    year_cluster['Median age'],
                    np.repeat(year, len(year_cluster)),
                ],
                axis=-1,
            ) if not year_cluster.empty else [],
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                'Year: %{customdata[3]}<br>'
                'Fertility: %{x:.1f} children/woman<br>'
                'Life expectancy: %{y:.1f} years<br>'
                'Median age: %{customdata[2]:.1f}<br>'
                'Population: %{customdata[1]:,.0f}'
                '<extra></extra>'
            ),
        )

    initial_year = years[0]
    fig = go.Figure(
        data=[make_trace(initial_year, label) for label in cluster_order],
        frames=[
            go.Frame(
                data=[make_trace(year, label) for label in cluster_order],
                name=str(year),
                traces=list(range(len(cluster_order))),
            )
            for year in years
        ],
    )

    slider_steps = [
        {
            'label': str(year),
            'method': 'animate',
            'args': [[str(year)], {
                'mode': 'immediate',
                'frame': {'duration': 0, 'redraw': True},
                'transition': {'duration': 0},
            }],
        }
        for year in years
    ]

    fig.update_layout(
        title='Demographic Transition: Fertility vs Life Expectancy',
        xaxis=dict(
            title='Fertility Rate (children/woman)',
            range=[0, 10],
            gridcolor=GRID_COLOR,
            zeroline=False,
            linecolor='#ccc',
        ),
        yaxis=dict(
            title='Life Expectancy (years)',
            range=[20, 90],
            gridcolor=GRID_COLOR,
            zeroline=False,
            linecolor='#ccc',
        ),
        height=600,
        hovermode='closest',
        updatemenus=[{
            'type': 'buttons',
            'direction': 'left',
            'showactive': False,
            'x': 0.02,
            'y': -0.16,
            'xanchor': 'left',
            'yanchor': 'top',
            'buttons': [
                {
                    'label': 'Play',
                    'method': 'animate',
                    'args': [None, {
                        'frame': {'duration': 420, 'redraw': True},
                        'transition': {'duration': 120},
                        'fromcurrent': True,
                        'mode': 'immediate',
                    }],
                },
                {
                    'label': 'Pause',
                    'method': 'animate',
                    'args': [[None], {
                        'frame': {'duration': 0, 'redraw': True},
                        'transition': {'duration': 0},
                        'mode': 'immediate',
                    }],
                },
            ],
        }],
        sliders=[{
            'active': 0,
            'currentvalue': {'prefix': 'Year: ', 'font': {'size': 13}},
            'pad': {'t': 45, 'b': 10},
            'steps': slider_steps,
        }],
    )
    return clean_template(fig)


def bubble_scatter_year(year: int = 2023, selected_countries: list = None,
                        highlight_war_torn: bool = False) -> go.Figure:
    """Static bubble scatter for a selected year. More reliable in Shiny than Plotly animation."""
    df = load_master_dataset()
    clusters = run_clustering()

    df_year = df[df['Year'] == year].copy()
    df_year = df_year[
        df_year['Code'].notna()
        & ~df_year['Code'].str.startswith('OWID').fillna(False)
        & (df_year['Code'].str.len() == 3)
    ]
    df_year = df_year.merge(clusters[['Entity', 'Cluster Label']], on='Entity', how='left')
    df_plot = df_year.dropna(subset=['Fertility rate', 'Life expectancy', 'Population', 'Cluster Label'])

    if selected_countries:
        df_plot = df_plot[df_plot['Entity'].isin(selected_countries)]

    # If highlighting war-torn: plot background countries at lower opacity, then overlay war-torn
    if highlight_war_torn:
        war_mask = df_plot['Entity'].isin(WAR_TORN)
        df_bg = df_plot[~war_mask]
        df_war = df_plot[war_mask]

        fig = px.scatter(
            df_bg,
            x='Fertility rate', y='Life expectancy',
            size='Population', color='Cluster Label',
            color_discrete_map=CLUSTER_COLORS,
            hover_name='Entity',
            hover_data={
                'Population': ':,', 'Median age': ':.1f',
                'Elderly share (%)': ':.1f', 'Children share (%)': ':.1f',
                'Code': False,
            },
            size_max=58, range_x=(0, 10), range_y=(20, 90),
            title=f'Fertility vs Life Expectancy — {year} (🔴 war-torn highlighted)',
            labels={
                'Fertility rate': 'Fertility Rate (children/woman)',
                'Life expectancy': 'Life Expectancy (years)',
            },
        )
        fig.update_traces(marker=dict(opacity=0.35, line=dict(width=0.3, color='#ccc')))

        if not df_war.empty:
            # Add war-torn overlay with red border + labels
            fig.add_trace(go.Scatter(
                x=df_war['Fertility rate'], y=df_war['Life expectancy'],
                mode='markers+text',
                marker=dict(
                    size=np.sqrt(df_war['Population'] / 1e6).clip(lower=6, upper=60),
                    color=[CLUSTER_COLORS.get(c, '#888') for c in df_war['Cluster Label']],
                    opacity=0.92,
                    line=dict(width=2.5, color='#e74c3c'),
                ),
                text=df_war['Entity'],
                textposition='top center',
                textfont=dict(size=10, color='#8B0000', family='Inter, sans-serif'),
                hovertext=df_war.apply(
                    lambda r: f"{r['Entity']}<br>Pop: {r['Population']:,.0f}<br>"
                              f"Fertility: {r['Fertility rate']:.1f}<br>LE: {r['Life expectancy']:.0f}",
                    axis=1,
                ),
                hoverinfo='text',
                name='War-torn',
                showlegend=True,
            ))
    else:
        fig = px.scatter(
            df_plot,
            x='Fertility rate', y='Life expectancy',
            size='Population', color='Cluster Label',
            color_discrete_map=CLUSTER_COLORS,
            hover_name='Entity',
            hover_data={
                'Population': ':,', 'Median age': ':.1f',
                'Elderly share (%)': ':.1f', 'Children share (%)': ':.1f',
                'Code': False,
            },
            size_max=58, range_x=(0, 10), range_y=(20, 90),
            title=f'Fertility vs Life Expectancy — {year}',
            labels={
                'Fertility rate': 'Fertility Rate (children/woman)',
                'Life expectancy': 'Life Expectancy (years)',
            },
        )
        fig.update_traces(marker=dict(opacity=0.78, line=dict(width=0.5, color='white')))

    fig.update_layout(height=520, legend=dict(orientation='h', y=-0.18))
    return clean_template(fig)


def global_trend_lines(compact: bool = False) -> go.Figure:
    """World average fertility and life expectancy over time."""
    df = load_master_dataset()
    world = df[df['Entity'] == 'World'].dropna(subset=['Fertility rate', 'Life expectancy'])

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    fig.add_trace(
        go.Scatter(
            x=world['Year'], y=world['Fertility rate'],
            name='Fertility rate', mode='lines',
            line=dict(color='#e74c3c', width=2.5),
            fill='tozeroy', fillcolor='rgba(231,76,60,0.1)',
            hovertemplate='Fertility: %{y:.2f}<extra></extra>',
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=world['Year'], y=world['Life expectancy'],
            name='Life expectancy', mode='lines',
            line=dict(color='#2ecc71', width=2.5),
            fill='tozeroy', fillcolor='rgba(46,204,113,0.1)',
            hovertemplate='Life expectancy: %{y:.1f} yrs<extra></extra>',
        ),
        secondary_y=True,
    )

    fig.update_xaxes(
        title_text='' if compact else 'Year',
        nticks=5 if compact else 8,
        tickfont=dict(size=10 if compact else 12),
    )
    fig.update_yaxes(
        title_text='' if compact else 'Fertility Rate (children/woman)',
        secondary_y=False,
        color='#e74c3c',
        range=[0, 6],
        tickfont=dict(size=10 if compact else 12),
    )
    fig.update_yaxes(
        title_text='' if compact else 'Life Expectancy (years)',
        secondary_y=True,
        color='#2ecc71',
        range=[0, 80],
        tickfont=dict(size=10 if compact else 12),
    )
    fig.update_layout(
        title='World Average: Fertility Rate & Life Expectancy (1950–2023)',
        height=225 if compact else 400,
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom' if compact else 'top',
            y=1.02 if compact else -0.18,
            x=0,
            xanchor='left',
            font=dict(size=10 if compact else 12),
        ),
        margin=dict(
            l=34 if compact else 20,
            r=34 if compact else 20,
            t=54 if compact else 50,
            b=28 if compact else 20,
        ),
    )
    fig = clean_template(fig)
    if compact:
        fig.update_layout(
            title=dict(text='Fertility down, longevity up', font=dict(size=13), x=0, xanchor='left'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, xanchor='left', font=dict(size=10)),
            margin=dict(l=34, r=34, t=54, b=28),
            hoverlabel=dict(bgcolor='white', bordercolor='#d0d5dd', font_size=11),
        )
    return fig


# ══════════════════════════════════════════════════════════════════════
# FINDING 2: AGING SOCIETIES
# ══════════════════════════════════════════════════════════════════════

def aging_line_chart(countries: list = None) -> go.Figure:
    """Fertility rate & median age lines for selected countries, with World average reference."""
    if countries is None:
        countries = ['Japan', 'South Korea', 'Afghanistan', 'Pakistan']

    df = load_master_dataset()
    cdf = df[df['Entity'].isin(countries)]
    world = df[df['Entity'] == 'World']

    fig = make_subplots(rows=1, cols=2, subplot_titles=('Fertility Rate', 'Median Age'))

    # World average — dashed reference in both subplots (added first so it's behind)
    w_fert = world.dropna(subset=['Fertility rate'])
    fig.add_trace(
        go.Scatter(x=w_fert['Year'], y=w_fert['Fertility rate'],
                   name='World avg', mode='lines',
                   line=dict(width=2.5, color='#333', dash='dash'),
                   legendgroup='World'),
        row=1, col=1,
    )
    w_age = world.dropna(subset=['Median age'])
    fig.add_trace(
        go.Scatter(x=w_age['Year'], y=w_age['Median age'],
                   name='World avg', mode='lines',
                   line=dict(width=2.5, color='#333', dash='dash'),
                   showlegend=False, legendgroup='World'),
        row=1, col=2,
    )

    # Country lines with distinct colors
    COUNTRY_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12',
                      '#8E44AD', '#1ABC9C', '#E67E22', '#E91E63']
    for i, country in enumerate(countries):
        color = COUNTRY_COLORS[i % len(COUNTRY_COLORS)]
        cd_fert = cdf[cdf['Entity'] == country].dropna(subset=['Fertility rate'])
        fig.add_trace(
            go.Scatter(x=cd_fert['Year'], y=cd_fert['Fertility rate'],
                       name=country, mode='lines',
                       line=dict(width=2, color=color)),
            row=1, col=1,
        )

        cd_age = cdf[cdf['Entity'] == country].dropna(subset=['Median age'])
        fig.add_trace(
            go.Scatter(x=cd_age['Year'], y=cd_age['Median age'],
                       name=country, mode='lines',
                       line=dict(width=2, color=color),
                       showlegend=False),
            row=1, col=2,
        )

    fig.update_xaxes(title_text='Year', row=1, col=1)
    fig.update_xaxes(title_text='Year', row=1, col=2)
    fig.update_yaxes(title_text='Children per woman', row=1, col=1)
    fig.update_yaxes(title_text='Years', row=1, col=2)
    fig.update_layout(
        title='Fertility Rate & Median Age — Country Comparison vs World Average',
        height=400,
    )
    return clean_template(fig)


def age_structure_stacked(country: str = 'Japan') -> go.Figure:
    """Stacked area chart of age structure groups over time."""
    df = load_master_dataset()
    cd = df[df['Entity'] == country].dropna(subset=['Children (0-14)', 'Working age (15-64)', 'Elderly (65+)'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cd['Year'], y=cd['Children (0-14)'],
        name='Children (0-14)', mode='lines', stackgroup='one',
        line=dict(width=0.5, color='#3498db'),
        fillcolor='rgba(52,152,219,0.6)',
    ))
    fig.add_trace(go.Scatter(
        x=cd['Year'], y=cd['Working age (15-64)'],
        name='Working age (15-64)', mode='lines', stackgroup='one',
        line=dict(width=0.5, color='#2ecc71'),
        fillcolor='rgba(46,204,113,0.6)',
    ))
    fig.add_trace(go.Scatter(
        x=cd['Year'], y=cd['Elderly (65+)'],
        name='Elderly (65+)', mode='lines', stackgroup='one',
        line=dict(width=0.5, color='#e74c3c'),
        fillcolor='rgba(231,76,60,0.6)',
    ))

    fig.update_layout(
        title=f'{country}: Age Structure Over Time',
        xaxis_title='Year', yaxis_title='Population',
        height=400, hovermode='x unified',
    )
    return clean_template(fig)


def elderly_ranking_bar(year: int = 2023, top_n: int = 15) -> go.Figure:
    """Horizontal bar chart of top countries by elderly share."""
    df = load_master_dataset()
    df_year = df[df['Year'] == year].dropna(subset=['Elderly share (%)'])

    # Filter to actual countries
    has_code = df_year['Code'].notna()
    df_year = df_year[has_code].copy()
    df_year = df_year[
        ~df_year['Code'].str.startswith('OWID')
        & (df_year['Code'].str.len() == 3)
    ]

    top = df_year.nlargest(top_n, 'Elderly share (%)')

    fig = px.bar(
        top.sort_values('Elderly share (%)'),
        x='Elderly share (%)', y='Entity',
        orientation='h',
        color='Elderly share (%)',
        color_continuous_scale='Reds',
        title=f'Top {top_n} Countries by Elderly Share — {year}',
        text=top['Elderly share (%)'].round(1),
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(height=400, yaxis=dict(autorange='reversed'))
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# FINDING 3: RAPID GROWTH
# ══════════════════════════════════════════════════════════════════════

def growth_line_chart(countries: list = None) -> go.Figure:
    """Population growth rate for young-growth countries."""
    if countries is None:
        countries = ['Nigeria', 'Ethiopia', 'Tanzania', 'Pakistan', 'Democratic Republic of Congo']

    df = load_master_dataset()
    cdf = df[df['Entity'].isin(countries)].dropna(subset=['Population growth rate'])

    fig = go.Figure()
    for country in countries:
        cd = cdf[cdf['Entity'] == country]
        fig.add_trace(go.Scatter(
            x=cd['Year'], y=cd['Population growth rate'],
            name=country, mode='lines', line=dict(width=2),
        ))

    # Add world average
    world = df[df['Entity'] == 'World'].dropna(subset=['Population growth rate'])
    fig.add_trace(go.Scatter(
        x=world['Year'], y=world['Population growth rate'],
        name='World average', mode='lines',
        line=dict(color='#172b45', width=2, dash='dash'),
    ))

    fig.update_layout(
        title='Young Populations: High Growth Rates vs World Average',
        xaxis_title='Year', yaxis_title='Population Growth Rate (%)',
        height=400, hovermode='x unified',
    )
    return clean_template(fig)


def children_share_bar(year: int = 2023, top_n: int = 15) -> go.Figure:
    """Bar chart of top countries by children share."""
    df = load_master_dataset()
    df_year = df[df['Year'] == year].dropna(subset=['Children share (%)'])

    has_code = df_year['Code'].notna()
    df_year = df_year[has_code].copy()
    df_year = df_year[
        ~df_year['Code'].str.startswith('OWID')
        & (df_year['Code'].str.len() == 3)
    ]

    top = df_year.nlargest(top_n, 'Children share (%)')

    fig = px.bar(
        top.sort_values('Children share (%)'),
        x='Children share (%)', y='Entity',
        orientation='h',
        color='Children share (%)',
        color_continuous_scale='Greens',
        title=f'Top {top_n} Countries by Children Share — {year}',
        text=top['Children share (%)'].round(1),
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(height=400, yaxis=dict(autorange='reversed'))
    return clean_template(fig)


def comparison_ranking_bar(indicator: str, year: int = 2023, compare_year: int = 1950,
                           top_n: int = 8, color_scale: str = 'Reds') -> go.Figure:
    """Grouped bar chart comparing top-N countries between two years for an indicator."""
    df = load_master_dataset()

    # Filter for both years
    df_both = df[(df['Year'].isin([compare_year, year]))].dropna(subset=[indicator])

    # Keep only country codes
    has_code = df_both['Code'].notna()
    df_both = df_both[has_code].copy()
    df_both = df_both[
        ~df_both['Code'].str.startswith('OWID')
        & (df_both['Code'].str.len() == 3)
    ]

    # Get top N in the selected year
    df_sel = df_both[df_both['Year'] == year]
    top_entities = df_sel.nlargest(top_n, indicator)['Entity'].tolist()

    # Keep only top entities for both years
    df_plot = df_both[df_both['Entity'].isin(top_entities)].copy()
    df_plot['Year'] = df_plot['Year'].astype(str)

    fig = px.bar(
        df_plot.sort_values(indicator, ascending=True),
        x=indicator, y='Entity',
        orientation='h', color='Year',
        barmode='group',
        color_discrete_map={str(compare_year): '#b0b0b0', str(year): '#e74c3c'},
        title=f'{indicator}: {compare_year} vs {year}',
    )
    fig.update_layout(height=400, yaxis=dict(autorange='reversed'))
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# FINDING 4: MIGRATION-SENSITIVE
# ══════════════════════════════════════════════════════════════════════

def migration_trend_chart(countries: list = None,
                         highlight_war_torn: bool = False) -> go.Figure:
    """Migrant stock trend lines for migration-sensitive countries."""
    if countries is None:
        countries = ['Ukraine', 'Syria', 'Venezuela', 'Afghanistan']

    df = load_master_dataset()
    indicator = 'Total number of international immigrants'

    # Collect all entities to show
    all_entities = set(countries)
    if highlight_war_torn:
        all_entities.update(WAR_TORN)

    # Filter to years where migration data exists (1990+)
    cdf = df[(df['Entity'].isin(all_entities)) & (df['Year'] >= 1990)].dropna(subset=[indicator])

    if cdf.empty:
        fig = go.Figure()
        fig.add_annotation(text='Migration data available from 1990 onwards',
                          x=0.5, y=0.5, showarrow=False, font=dict(color=FONT_COLOR))
        fig.update_layout(height=350)
        return clean_template(fig)

    # Build a color map: selected countries get palette colors, war-torn get red tones
    MIG_PALETTE = [
        '#1e3a5f', '#2ecc71', '#f39c12', '#8E44AD', '#1ABC9C',
        '#E67E22', '#3498db', '#E91E63', '#00BCD4', '#27AE60',
    ]
    color_map = {}
    selected_list = sorted(countries)
    for i, c in enumerate(selected_list):
        color_map[c] = MIG_PALETTE[i % len(MIG_PALETTE)]

    fig = go.Figure()
    for entity in sorted(all_entities):
        cd = cdf[cdf['Entity'] == entity]
        if len(cd) == 0:
            continue
        is_war = entity in WAR_TORN
        is_selected = entity in countries
        if is_war and not is_selected:
            # War-torn reference line: faded red dotted (not in legend)
            fig.add_trace(go.Scatter(
                x=cd['Year'], y=cd[indicator],
                name=f'{entity} (war-torn)', mode='lines',
                line=dict(width=0.8, color='rgba(231,76,60,0.4)', dash='dot'),
                showlegend=False,
            ))
        elif is_war and is_selected:
            # War-torn AND selected: keep its assigned color but with red accent
            line_color = color_map.get(entity, '#e74c3c')
            fig.add_trace(go.Scatter(
                x=cd['Year'], y=cd[indicator],
                name=f'🔴 {entity}', mode='lines+markers',
                line=dict(width=2.8, color=line_color),
                marker=dict(size=6, color=line_color, line=dict(width=1.5, color='#e74c3c')),
            ))
        else:
            # Normal selected country: palette color
            line_color = color_map.get(entity, '#333')
            fig.add_trace(go.Scatter(
                x=cd['Year'], y=cd[indicator],
                name=entity, mode='lines+markers',
                line=dict(width=2, color=line_color),
                marker=dict(size=4, color=line_color),
            ))

    latest_year = int(cdf['Year'].max())
    title = f'International Migrant Stock (1990-{latest_year})'
    if highlight_war_torn:
        title += ' — 🔴 war-torn highlighted'
    fig.update_layout(
        title=title,
        xaxis_title='Year', yaxis_title='Total International Immigrants',
        height=400, hovermode='x unified',
    )
    return clean_template(fig)


def disruption_dashboard_chart(selected_country: str = 'Ukraine') -> go.Figure:
    """Multi-panel view: population growth, death rate, life expectancy."""
    df = load_master_dataset()
    cd = df[(df['Entity'] == selected_country) & (df['Year'] >= 1950)]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Population Growth Rate', 'Life Expectancy',
                        'Crude Death Rate', 'Migrant Stock'),
    )

    # Pop growth
    pg = cd.dropna(subset=['Population growth rate'])
    fig.add_trace(
        go.Scatter(x=pg['Year'], y=pg['Population growth rate'], mode='lines',
                   line=dict(color='#3498db', width=2), showlegend=False),
        row=1, col=1,
    )

    # Life expectancy
    le = cd.dropna(subset=['Life expectancy'])
    fig.add_trace(
        go.Scatter(x=le['Year'], y=le['Life expectancy'], mode='lines',
                   line=dict(color='#2ecc71', width=2), showlegend=False),
        row=1, col=2,
    )

    # Death rate
    dr = cd.dropna(subset=['Annual crude death rate'])
    fig.add_trace(
        go.Scatter(x=dr['Year'], y=dr['Annual crude death rate'], mode='lines',
                   line=dict(color='#e74c3c', width=2), showlegend=False),
        row=2, col=1,
    )

    # Migrant stock
    ms = cd[(cd['Year'] >= 1990)].dropna(subset=['Total number of international immigrants'])
    fig.add_trace(
        go.Scatter(x=ms['Year'], y=ms['Total number of international immigrants'],
                   mode='lines+markers', line=dict(color='#f39c12', width=2), showlegend=False),
        row=2, col=2,
    )

    fig.update_xaxes(title_text='Year', row=1, col=1)
    fig.update_xaxes(title_text='Year', row=1, col=2)
    fig.update_xaxes(title_text='Year', row=2, col=1)
    fig.update_xaxes(title_text='Year', row=2, col=2)

    title = f'{selected_country}: Demographic Disruption Patterns'
    if selected_country in WAR_TORN:
        title = f'⚠️ {selected_country}: Conflict-Affected Demographic Disruption'
    fig.update_layout(
        title=title,
        height=500,
    )
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# FINDING 5: SIMILAR DEMOGRAPHIC FUTURES (ML)
# ══════════════════════════════════════════════════════════════════════

def cluster_pca_scatter(year: int = 2023, highlight_war_torn: bool = False) -> go.Figure:
    """PCA scatter plot of countries colored by cluster, with optional war-torn highlight."""
    clusters = run_clustering()

    if highlight_war_torn:
        war_mask = clusters['Entity'].isin(WAR_TORN)
        clusters_bg = clusters[~war_mask]
        clusters_war = clusters[war_mask]

        fig = px.scatter(
            clusters_bg,
            x='PCA_x', y='PCA_y',
            color='Cluster Label',
            color_discrete_map=CLUSTER_COLORS,
            hover_name='Entity',
            hover_data={
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                'Median age': ':.1f',
                'PCA_x': False, 'PCA_y': False,
            },
            title=f'Demographic Clusters (PCA) — {year} (🔴 war-torn highlighted)',
            labels={'PCA_x': 'PC1', 'PCA_y': 'PC2'},
        )
        fig.update_traces(marker=dict(size=10, opacity=0.3, line=dict(width=0.3, color='#ccc')))

        if not clusters_war.empty:
            fig.add_trace(go.Scatter(
                x=clusters_war['PCA_x'], y=clusters_war['PCA_y'],
                mode='markers+text',
                marker=dict(
                    size=14, opacity=0.95,
                    color=[CLUSTER_COLORS.get(c, '#888') for c in clusters_war['Cluster Label']],
                    line=dict(width=2.2, color='#e74c3c'),
                ),
                text=clusters_war['Entity'],
                textposition='top center',
                textfont=dict(size=9, color='#8B0000', family='Inter, sans-serif'),
                hovertext=clusters_war.apply(
                    lambda r: f"{r['Entity']}<br>Cluster: {r['Cluster Label']}<br>"
                              f"Fertility: {r['Fertility rate']:.1f}<br>LE: {r['Life expectancy']:.0f}",
                    axis=1,
                ),
                hoverinfo='text',
                name='War-torn',
                showlegend=True,
            ))
    else:
        fig = px.scatter(
            clusters,
            x='PCA_x', y='PCA_y',
            color='Cluster Label',
            color_discrete_map=CLUSTER_COLORS,
            hover_name='Entity',
            hover_data={
                'Fertility rate': ':.1f',
                'Life expectancy': ':.1f',
                'Median age': ':.1f',
                'PCA_x': False, 'PCA_y': False,
            },
            title=f'Demographic Clusters (PCA) — {year}',
            labels={'PCA_x': 'PC1', 'PCA_y': 'PC2'},
        )
        fig.update_traces(marker=dict(size=10, opacity=0.8, line=dict(width=0.5, color='white')))

    fig.update_layout(height=550)
    return clean_template(fig)


def _legacy_similar_countries_profile_bar(country: str, top_n: int = 5) -> go.Figure:
    """Radar chart comparing a country with its top similar countries."""
    from .ml_clustering import get_similar_countries

    similar = get_similar_countries(country, top_n=top_n)
    countries_to_compare = [country] + similar['Entity'].tolist()

    df = load_master_dataset()
    df_2023 = df[df['Year'] == 2023]

    radar_features = [
        'Fertility rate',
        'Life expectancy',
        'Median age',
        'Elderly share (%)',
        'Children share (%)',
    ]

    all_countries = df_2023[df_2023['Entity'].isin(countries_to_compare)].dropna(subset=radar_features)
    if all_countries.empty or country not in all_countries['Entity'].values:
        fig = go.Figure()
        fig.add_annotation(text=f'No similarity profile available for {country}', x=0.5, y=0.5, showarrow=False)
        return clean_template(fig)

    global_values = df_2023.dropna(subset=radar_features)[radar_features]
    country_values = all_countries[all_countries['Entity'] == country].iloc[0][radar_features]
    peer_values = all_countries[all_countries['Entity'] != country][radar_features].mean()

    normalized_country = (country_values - global_values.min()) / (global_values.max() - global_values.min() + 1e-10)
    normalized_peers = (peer_values - global_values.min()) / (global_values.max() - global_values.min() + 1e-10)

    display_names = ['Fertility', 'Life expectancy', 'Median age', 'Elderly share', 'Children share']
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=display_names,
        x=normalized_peers.values,
        orientation='h',
        name=f'Top {len(similar)} similar avg',
        marker=dict(color='rgba(52,152,219,0.35)'),
        hovertemplate='%{y}<br>Peer avg normalized: %{x:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        y=display_names,
        x=normalized_country.values,
        orientation='h',
        name=country,
        marker=dict(color='#1e3a5f'),
        hovertemplate='%{y}<br>Selected country normalized: %{x:.2f}<extra></extra>',
    ))
    fig.update_layout(
        title=f'{country} vs Similar-Country Average - Normalized Profile',
        barmode='group',
        xaxis_title='Normalized value across all countries (0-1)',
        yaxis_title='',
        xaxis=dict(range=[0, 1]),
        height=500,
        legend=dict(orientation='h', y=-0.18),
    )
    fig.update_yaxes(autorange='reversed')
    return clean_template(fig)

    # Normalize values for radar (min-max per feature)
    all_vals = df_2023[df_2023['Entity'].isin(countries_to_compare)][radar_features]
    normalized = (all_vals - all_vals.min()) / (all_vals.max() - all_vals.min() + 1e-10)

    fig = go.Figure()
    colors = ['white', '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']

    for i, c in enumerate(countries_to_compare):
        row = df_2023[df_2023['Entity'] == c]
        if row.empty:
            continue
        vals = normalized[normalized.index == row.index[0]].values[0]
        fig.add_trace(go.Scatterpolar(
            r=vals.tolist(),
            theta=radar_features,
            name=c,
            fill='toself' if c == country else 'none',
            line=dict(color=colors[i % len(colors)], width=2.5 if c == country else 1.5),
            opacity=1 if c == country else 0.5,
        ))

    fig.update_layout(
        title=f'{country} vs Similar Countries — Demographic Profile',
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
            bgcolor='rgba(40,40,40,1)',
        ),
        height=500,
        legend=dict(orientation='h', y=-0.1),
    )
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# COUNTRY EXPLORER
# ══════════════════════════════════════════════════════════════════════

def similar_countries_radar(country: str, top_n: int = 5) -> go.Figure:
    """Bright radar chart comparing a country with its top similar countries."""
    from .ml_clustering import get_similar_countries

    similar = get_similar_countries(country, top_n=top_n)
    countries_to_compare = [country] + similar['Entity'].tolist()

    df = load_master_dataset()
    df_2023 = df[df['Year'] == 2023]
    radar_features = [
        'Fertility rate',
        'Life expectancy',
        'Median age',
        'Elderly share (%)',
        'Children share (%)',
    ]
    theta_labels = ['Fertility', 'Life expectancy', 'Median age', 'Elderly share', 'Children share']

    profile_df = df_2023[df_2023['Entity'].isin(countries_to_compare)].dropna(subset=radar_features)
    if profile_df.empty or country not in profile_df['Entity'].values:
        fig = go.Figure()
        fig.add_annotation(
            text=f'No similarity profile available for {country}',
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return clean_template(fig)

    global_values = df_2023.dropna(subset=radar_features)[radar_features]
    normalized = (
        (profile_df.set_index('Entity')[radar_features] - global_values.min())
        / (global_values.max() - global_values.min() + 1e-10)
    )

    fig = go.Figure()
    colors = ['#12355b', '#e74c3c', '#2f80ed', '#27ae60', '#f39c12', '#8e44ad']

    for i, c in enumerate(countries_to_compare):
        if c not in normalized.index:
            continue

        vals = normalized.loc[c].values.tolist()
        vals_closed = vals + [vals[0]]
        theta_closed = theta_labels + [theta_labels[0]]
        is_main = c == country

        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=theta_closed,
            name=c,
            fill='toself' if is_main else 'none',
            fillcolor='rgba(18,53,91,0.16)' if is_main else 'rgba(0,0,0,0)',
            line=dict(color=colors[i % len(colors)], width=3.5 if is_main else 2),
            marker=dict(size=5 if is_main else 4),
            opacity=1 if is_main else 0.68,
            hovertemplate='%{theta}<br>Normalized score: %{r:.2f}<extra>' + c + '</extra>',
        ))

    clean_template(fig)
    fig.update_layout(
        title=f'{country} vs Similar Countries - Demographic Radar Profile',
        polar=dict(
            bgcolor='#ffffff',
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0, 0.25, 0.5, 0.75, 1],
                tickfont=dict(color='#667085', size=10),
                gridcolor='#d9e2ec',
                linecolor='#b6c2cf',
            ),
            angularaxis=dict(
                gridcolor='#d9e2ec',
                linecolor='#b6c2cf',
                tickfont=dict(color='#172b45', size=11),
            ),
        ),
        height=500,
        legend=dict(orientation='h', y=-0.18, x=0, font=dict(size=11)),
        margin=dict(l=35, r=35, t=65, b=90),
    )
    return fig


def country_multi_line(country: str, compare_countries: list = None) -> go.Figure:
    """Multi-indicator line chart for a country with optional comparison."""
    indicators = ['Fertility rate', 'Life expectancy', 'Median age', 'Population growth rate']
    MAIN_COLOR = '#1e3a5f'  # consistent brand color for the primary country

    # Distinct palette for comparison countries — each country gets its own color
    compare_palette = [
        '#e74c3c', '#2ecc71', '#f39c12', '#8E44AD', '#1ABC9C',
        '#E67E22', '#E91E63', '#00BCD4', '#FF9800', '#9C27B0',
    ]

    all_countries = [country]
    if compare_countries:
        all_countries.extend(compare_countries)

    # Build a color map: main → MAIN_COLOR, compare → palette color
    cmp_colors = {country: MAIN_COLOR}
    for i, cnt in enumerate(compare_countries or []):
        cmp_colors[cnt] = compare_palette[i % len(compare_palette)]

    df = load_master_dataset()
    cdf = df[df['Entity'].isin(all_countries)]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=indicators,
    )

    for idx, ind in enumerate(indicators):
        row, col = idx // 2 + 1, idx % 2 + 1
        for cnt in all_countries:
            cd = cdf[(cdf['Entity'] == cnt) & (df['Year'] >= 1950)].dropna(subset=[ind])
            if cd.empty:
                continue
            is_main = cnt == country
            line_color = cmp_colors.get(cnt, '#999')
            line_width = 2.8 if is_main else 1.3
            line_dash = 'solid' if is_main else 'dash'
            fig.add_trace(
                go.Scatter(
                    x=cd['Year'], y=cd[ind],
                    name=cnt, mode='lines',
                    line=dict(color=line_color, width=line_width, dash=line_dash),
                    showlegend=(idx == 0),
                    legendgroup=cnt,
                ),
                row=row, col=col,
            )

        fig.update_xaxes(title_text='Year', row=row, col=col)

    fig.update_layout(
        title=f'{country}: Demographic Profile',
        height=550, hovermode='x unified',
    )
    return clean_template(fig)


def country_forecast_chart(country: str, indicator: str = 'Median age') -> go.Figure:
    """Historical + forecast line for a country-indicator pair."""
    result = forecast_indicator(country, indicator)

    if 'error' in result:
        fig = go.Figure()
        fig.add_annotation(text=result['error'], x=0.5, y=0.5, showarrow=False,
                          font=dict(color=FONT_COLOR))
        return clean_template(fig)

    ci = 1.96 * max(0.2, 1 - max(result['r2_score'], 0)) * np.std(result['historical_values'])

    fig = go.Figure()

    # Historical
    fig.add_trace(go.Scatter(
        x=result['historical_years'], y=result['historical_values'],
        name='Historical', mode='lines',
        line=dict(color='#3498db', width=2.5),
    ))

    # Forecast
    fig.add_trace(go.Scatter(
        x=result['forecast_years'], y=result['forecast_values'],
        name='Simple trend projection', mode='lines',
        line=dict(color='#f39c12', width=2.5, dash='dash'),
    ))

    # Confidence band
    fig.add_trace(go.Scatter(
        x=result['forecast_years'] + result['forecast_years'][::-1],
        y=[fv + ci for fv in result['forecast_values']]
          + [fv - ci for fv in result['forecast_values'][::-1]],
        fill='toself', fillcolor='rgba(243,156,18,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Approx. uncertainty band',
    ))

    fig.update_layout(
        title=f'{country}: {indicator} - Historical & Simple Projection',
        xaxis_title='Year', yaxis_title=indicator,
        height=400, hovermode='x unified',
    )
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# FORECAST TAB CHARTS
# ══════════════════════════════════════════════════════════════════════

FORECAST_PALETTE = [
    '#1e3a5f', '#e74c3c', '#2ecc71', '#f39c12', '#8E44AD',
    '#1ABC9C', '#E67E22', '#3498db', '#E91E63', '#00BCD4',
]


def forecast_multi_country(countries: list, indicator: str = 'Median age',
                           forecast_years: int = 15) -> go.Figure:
    """Multi-country historical + forecast lines for one indicator."""
    fig = go.Figure()

    for i, cnt in enumerate(countries):
        result = forecast_indicator(cnt, indicator, forecast_years)
        if 'error' in result:
            continue
        color = FORECAST_PALETTE[i % len(FORECAST_PALETTE)]

        # Historical
        fig.add_trace(go.Scatter(
            x=result['historical_years'], y=result['historical_values'],
            name=cnt, mode='lines',
            line=dict(color=color, width=2.2),
            legendgroup=cnt,
            showlegend=True,
        ))

        # Forecast (dashed, same color)
        fig.add_trace(go.Scatter(
            x=result['forecast_years'], y=result['forecast_values'],
            name=f'{cnt} (forecast)', mode='lines',
            line=dict(color=color, width=2.2, dash='dash'),
            legendgroup=cnt,
            showlegend=False,
        ))

        # Divider line between historical and forecast
        if result['historical_years'] and result['forecast_years']:
            last_hist_year = result['historical_years'][-1]
            fig.add_vline(
                x=last_hist_year, line_dash='dot', line_color='#999',
                line_width=1, opacity=0.5,
            )

    fig.update_layout(
        title=f'{indicator}: Historical & Projection ({forecast_years}-year trend)',
        xaxis_title='Year', yaxis_title=indicator,
        height=500, hovermode='x unified',
    )
    return clean_template(fig)


def forecast_table(countries: list, indicator: str = 'Median age',
                   forecast_years: int = 15, target_years: list = None) -> go.Figure:
    """Table showing projected values at milestone years for selected countries."""
    if target_years is None:
        target_years = [2030, 2035, 2040]

    rows = []
    for cnt in countries:
        result = forecast_indicator(cnt, indicator, forecast_years)
        if 'error' in result:
            continue
        latest_hist = result['historical_values'][-1] if result['historical_values'] else None
        last_hist_year = result['historical_years'][-1] if result['historical_years'] else None
        trend = result['trend_coef']
        r2 = result['r2_score']

        row = [cnt, f'{latest_hist:.1f}' if latest_hist else '-',
               f'{trend:+.3f}/yr', f'{r2:.2f}']
        for ty in target_years:
            if ty in result['forecast_years']:
                idx = result['forecast_years'].index(ty)
                row.append(f'{result["forecast_values"][idx]:.1f}')
            else:
                row.append('-')
        rows.append(row)

    headers = ['Country', f'Latest ({last_hist_year})', 'Trend', 'R²'] + [str(y) for y in target_years]

    fig = go.Figure(data=[go.Table(
        header=dict(values=headers, fill_color='#1e3a5f',
                   font=dict(color='white', size=11), align='center',
                   line_color='#ddd', height=34),
        cells=dict(values=list(zip(*rows)), fill_color='white',
                  font=dict(color='#333', size=11), align='center',
                  height=30, line_color='#eee',
                  format=[None, None, None, None] + [None] * len(target_years)),
    )])
    fig.update_layout(
        title=f'{indicator}: Projected Values',
        height=200 + 35 * len(rows),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return clean_template(fig)


def forecast_trend_bar(indicator: str = 'Median age', top_n: int = 12,
                       forecast_years: int = 15, ascending: bool = False) -> go.Figure:
    """Horizontal bar chart ranking countries by forecast trend slope."""
    df = load_master_dataset()
    # Get countries with valid data
    recent = df[(df['Year'] == 2023)].dropna(subset=[indicator])
    has_code = recent['Code'].notna()
    recent = recent[has_code]
    recent = recent[~recent['Code'].str.startswith('OWID') & (recent['Code'].str.len() == 3)]

    results = []
    for _, row in recent.iterrows():
        cnt = row['Entity']
        if cnt == 'World':
            continue
        fc = forecast_indicator(cnt, indicator, forecast_years)
        if 'error' not in fc:
            results.append({
                'country': cnt,
                'trend': fc['trend_coef'],
                'r2': fc['r2_score'],
                'latest': fc['historical_values'][-1] if fc['historical_values'] else None,
            })

    results_df = pd.DataFrame(results)
    if results_df.empty:
        fig = go.Figure()
        fig.add_annotation(text='No forecast data available', x=0.5, y=0.5, showarrow=False)
        return clean_template(fig)

    top = results_df.nlargest(top_n, 'trend') if not ascending else results_df.nsmallest(top_n, 'trend')
    direction = 'Rising Fastest' if not ascending else 'Falling Fastest'

    fig = px.bar(
        top.sort_values('trend'),
        x='trend', y='country', orientation='h',
        color='trend', color_continuous_scale='RdBu' if not ascending else 'RdBu_r',
        title=f'{indicator}: {direction} ({forecast_years}-year trend)',
        text=top['trend'].apply(lambda x: f'{x:+.3f}/yr'),
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis_title='Trend slope (per year)',
        yaxis_title='',
        height=400,
        yaxis=dict(autorange='reversed'),
    )
    return clean_template(fig)


# ══════════════════════════════════════════════════════════════════════
# INSIGHT TEXT GENERATOR
# ══════════════════════════════════════════════════════════════════════

def generate_country_insight(country: str, year: int = 2023) -> str:
    """Auto-generate insight text for a country based on its demographic profile."""
    from .ml_clustering import get_demographic_profile

    profile = get_demographic_profile(country, year)
    if 'error' in profile:
        return f'No data available for {country}.'

    cluster = profile.get('Cluster', 'Unknown group')
    fert = profile.get('Fertility rate', 'N/A')
    le = profile.get('Life expectancy', 'N/A')
    elderly = profile.get('Elderly share (%)', 'N/A')
    growth = profile.get('Population growth rate', 'N/A')
    similar = profile.get('Similar countries', [])

    similar_str = ', '.join(similar[:3]) if similar else 'various countries'

    insight = (
        f"**{country}** belongs to the **{cluster}** group. "
        f"It has a fertility rate of **{fert}** children per woman, "
        f"life expectancy of **{le}** years, and an elderly share of **{elderly}**. "
        f"Population growth is **{growth}**. "
        f"Demographically similar countries include: **{similar_str}**."
    )

    return insight


if __name__ == "__main__":
    print("Testing charts module...")
    print("- world_map_chart: OK")
    print("- finding_cards_data:", len(finding_cards_data()))
    print("- Similar radar for Japan:")
    fig = similar_countries_radar('Japan')
    print(f"  {len(fig.data)} traces")
    print("- Country insight for Vietnam:")
    print(generate_country_insight('Vietnam'))
