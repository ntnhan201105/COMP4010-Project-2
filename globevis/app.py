from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import os


# --- Load Data ---
df_full = pd.read_parquet("./data/demographics.parquet")
min_year = int(df_full['year'].min())
max_year = int(df_full['year'].max())

# --- Load History ---
history_db = {}
history_path = "./data/historical_events.json"
if os.path.exists(history_path):
    with open(history_path, "r", encoding="utf-8") as f:
        history_db = json.load(f)


# --- Dashboard UI Definition ---
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Interactive 3D Globe",
        ui.div(
            ui.div(id="deck-map-container", style="width: 100%; height: 82vh;"),
            ui.output_ui("deep_dive_panel"),
            ui.tags.button(
                ui.HTML('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-map" style="margin-right: 6px;"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg> 2D Map'),
                id="view-toggle-btn",
                class_="view-toggle-btn"
            ),
            style="position: relative; width: 100%; height: 82vh;"
        )
    ),
    ui.nav_panel(
        "2D Analytics and Deep Dives",
        ui.layout_columns(
            ui.card(
                ui.card_header("Population Pyramid Proxy"),
                output_widget("population_pyramid")
            ),
            ui.card(
                ui.card_header("Historical Trend"),
                output_widget("historical_trend")
            )
        )
    ),
    sidebar=ui.sidebar(
        ui.h2("Global Demographics", class_="mb-4"),
        
        ui.input_slider("timeline_year", "Select Year", min=min_year, max=max_year, value=max_year, step=1, animate=ui.AnimationOptions(loop=False), sep=""),
        ui.input_select(
            "indicator", 
            "Visualized Indicator", 
            choices={
                "life_expectancy": "Life Expectancy",
                "fertility_rate": "Fertility Rate",
                "net_migration": "Net Migration Flows"
            }
        ),
        
        ui.hr(),
        
        # Reactive text exposition section replacing the Guided Tours
        ui.output_ui("indicator_exposition"),
        
        width=400,
        open="desktop",
    ),
    title="Demographic Globe Explorer",
    id="main_nav",
    header=ui.TagList(
        ui.head_content(
            ui.tags.script(src="https://unpkg.com/deck.gl@8.9.0/dist.min.js"),
            ui.include_css("www/style.css"),
            ui.include_css("www/deep_dive.css")
        ),
        ui.include_js("www/deck_map.js")
    ),
)

# --- Dashboard Server Logic ---
def server(input, output, session):
    
    selected_country = reactive.Value(None)
    
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
    def deep_dive_panel():
        iso = selected_country.get()
        if not iso:
            return None
            
        country_df = df_full[df_full['iso_alpha'] == iso]
        if country_df.empty:
            return None
            
        country_name = country_df['country'].iloc[0]
        
        return ui.div(
            ui.div(
                ui.h4(country_name, class_="deep-dive-title"),
                ui.input_action_button("close_deep_dive", "✕", class_="deep-dive-close"),
                class_="deep-dive-header"
            ),
            ui.output_ui("deep_dive_year_text"),
            ui.div(
                output_widget("deep_dive_plot"),
                class_="deep-dive-plot"
            ),
            ui.output_ui("deep_dive_history_text"),
            class_="deep-dive-panel"
        )

    @render.ui
    def deep_dive_year_text():
        iso = selected_country.get()
        if not iso:
            return None
        country_df = df_full[df_full['iso_alpha'] == iso]
        if country_df.empty:
            return None
        country_name = country_df['country'].iloc[0]
        year = input.timeline_year()
        return ui.div(
            f"Detailed historical trend for {country_name}. The marker indicates the currently selected year ({year}).",
            class_="deep-dive-content"
        )

    @render.ui
    def deep_dive_history_text():
        iso = selected_country.get()
        if not iso or iso not in history_db:
            return None
            
        year = input.timeline_year()
        country_history = history_db[iso]
        
        # Find the period that covers the selected year
        current_period = None
        for p in country_history:
            if p["start"] <= year <= p["end"]:
                current_period = p
                break
                
        if not current_period:
            return None
            
        return ui.div(
            ui.div(
                ui.span(f"Period {current_period['start']}-{current_period['end']} Context:", class_="history-period-label"),
                ui.span(current_period["period"], class_="history-period-title"),
                class_="history-header-block"
            ),
            ui.p(current_period["details"], class_="history-details"),
            ui.div(
                ui.span(current_period['source'], class_="history-source"),
                class_="history-footer"
            ),
            class_="vn-history-box"
        )

    # High-performance FigureWidget
    deep_dive_fig = go.FigureWidget()
    deep_dive_fig.update_layout(
        template="plotly_dark", 
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        height=200
    )
    deep_dive_fig.add_scatter(x=[], y=[], mode='lines', line=dict(color='#818cf8', width=2))
    deep_dive_fig.add_vline(x=1950, line_width=2, line_dash="dash", line_color="#ef4444")

    @render_widget
    def deep_dive_plot():
        # Only returns the widget container once. Updates happen via reactive effects.
        return deep_dive_fig

    @reactive.Effect
    def _update_deep_dive_data():
        iso = selected_country.get()
        if not iso:
            return
            
        indicator = input.indicator()
        if indicator == "life_expectancy":
            col = "lifeExp"
            title = "Life Expectancy"
        elif indicator == "fertility_rate":
            col = "fertility_rate"
            title = "Fertility Rate"
        else:
            col = "net_migration"
            title = "Net Migration"
            
        country_df = df_full[df_full['iso_alpha'] == iso]
        
        with deep_dive_fig.batch_update():
            deep_dive_fig.data[0].x = country_df['year']
            deep_dive_fig.data[0].y = country_df[col]
            deep_dive_fig.layout.title = title

    @reactive.Effect
    def _update_deep_dive_year():
        # Update the vertical line position continuously without re-rendering the plot
        year = input.timeline_year()
        if len(deep_dive_fig.layout.shapes) > 0:
            with deep_dive_fig.batch_update():
                deep_dive_fig.layout.shapes[0].x0 = year
                deep_dive_fig.layout.shapes[0].x1 = year

    @render.ui
    def indicator_exposition():
        ind = input.indicator()
        if ind == "life_expectancy":
            return ui.TagList(
                ui.h4("About Life Expectancy", class_="exposition-title"),
                ui.p("Life expectancy measures the average number of years a newborn would live if mortality patterns remained constant. Historically, this has risen dramatically across the globe due to advances in sanitation, vaccines, and modern medicine."),
                
                ui.h5("Map Legend:"),
                ui.div(
                    ui.div(style="height: 12px; border-radius: 6px; background: linear-gradient(to right, #ef4444, #fbbf24, #10d97a); margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1);"),
                    ui.div(
                        ui.span("40 yrs (Low)", style="font-size: 0.8rem; color: #ef4444; font-weight: 600;"),
                        ui.span("62 yrs", style="font-size: 0.8rem; color: #fbbf24; font-weight: 600; position: absolute; left: 50%; transform: translateX(-50%);"),
                        ui.span("85+ yrs (High)", style="font-size: 0.8rem; color: #10d97a; font-weight: 600; float: right;"),
                        style="position: relative; overflow: visible;"
                    ),
                    style="margin-top: 10px; margin-bottom: 20px;"
                ),
                
                ui.h5("Global Trends & Insights:"),
                ui.tags.ul(
                    ui.tags.li(ui.strong("Vibrant Emerald:"), " Indicates high life expectancy (80+ years) typically found in developed nations across Europe, North America, and parts of East Asia."),
                    ui.tags.li(ui.strong("Warm Orange-Red:"), " Highlights regions facing demographic bottlenecks or public health infrastructure challenges (typically under 60 years).")
                )
            )
        elif ind == "fertility_rate":
            return ui.TagList(
                ui.h4("About Fertility Rate", class_="exposition-title"),
                ui.p("The fertility rate represents the average number of children born to a woman over her lifetime. A rate of 2.1 is generally considered the 'replacement level' needed to keep a population stable without migration."),
                
                ui.h5("Map Legend:"),
                ui.div(
                    ui.div(style="height: 12px; border-radius: 6px; background: linear-gradient(to right, #06c8f0, #8b3ff5, #f024a0); margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1);"),
                    ui.div(
                        ui.span("1.0 (Low)", style="font-size: 0.8rem; color: #06c8f0; font-weight: 600;"),
                        ui.span("4.0", style="font-size: 0.8rem; color: #8b3ff5; font-weight: 600; position: absolute; left: 50%; transform: translateX(-50%);"),
                        ui.span("7.0+ (High)", style="font-size: 0.8rem; color: #f024a0; font-weight: 600; float: right;"),
                        style="position: relative; overflow: visible;"
                    ),
                    style="margin-top: 10px; margin-bottom: 20px;"
                ),
                
                ui.h5("Global Trends & Insights:"),
                ui.tags.ul(
                    ui.tags.li(ui.strong("Cool Cyan:"), " Represents sub-replacement levels (under 1.5 births per woman). Rapidly aging societies like Japan, South Korea, and parts of Europe fall in this category."),
                    ui.tags.li(ui.strong("Vibrant Magenta:"), " Indicates high fertility rates (4.0+ births per woman), which drive rapid youth-led growth, primarily centered in Sub-Saharan Africa.")
                )
            )
        else:
            return ui.TagList(
                ui.h4("About Net Migration Flows", class_="exposition-title"),
                ui.p("Net migration measures the difference between immigration (inflow) and emigration (outflow) per country in the selected year. It serves as a vital barometer for economic opportunity and geopolitical stability."),
                
                ui.h5("Map Legend:"),
                ui.div(
                    ui.div(style="height: 12px; border-radius: 6px; background: linear-gradient(to right, #f02840, #161c34, #00d2ff); margin-bottom: 8px; border: 1px solid rgba(255,255,255,0.1);"),
                    ui.div(
                        ui.span("Emigration", style="font-size: 0.8rem; color: #f02840; font-weight: 600;"),
                        ui.span("Neutral", style="font-size: 0.8rem; color: #94a3b8; font-weight: 500; position: absolute; left: 50%; transform: translateX(-50%);"),
                        ui.span("Immigration", style="font-size: 0.8rem; color: #00d2ff; font-weight: 600; float: right;"),
                        style="position: relative; overflow: visible; height: 20px;"
                    ),
                    style="margin-top: 10px; margin-bottom: 20px;"
                ),
                
                ui.h5("Global Trends & Insights:"),
                ui.tags.ul(
                    ui.tags.li(ui.strong("Bright Cyan/Teal:"), " Signals net positive immigration. Major economic magnets include the United States, parts of Western Europe, and the Persian Gulf nations."),
                    ui.tags.li(ui.strong("Vibrant Red:"), " Indicates significant net emigration, often corresponding directly to sudden political crises, conflicts, or severe economic contractions.")
                )
            )

    @reactive.Effect
    async def send_deck_data():
        year = input.timeline_year()
        indicator = input.indicator()
        df_year = df_full[df_full['year'] == year].copy()

        if indicator == "life_expectancy":
            df_year['raw_value'] = df_year['lifeExp']
            t = ((df_year['lifeExp'].clip(40, 85) - 40) / 45).values

            # 3-stop gradient: vivid red -> warm amber -> bright emerald
            # Routing through amber avoids the muddy RGB midpoint between red & green
            # Stop 0 (t=0.0): #ef4444  (239,  68,  68) -- vibrant red
            # Stop 1 (t=0.5): #fbbf24  (251, 191,  36) -- warm amber
            # Stop 2 (t=1.0): #10d97a  ( 16, 217, 122) -- bright emerald
            t2  = np.clip(t * 2, 0, 1)           # 0->1 for first half
            t2h = np.clip((t - 0.5) * 2, 0, 1)  # 0->1 for second half

            r = np.where(t < 0.5, 239 + (251 - 239) * t2,  251 + ( 16 - 251) * t2h)
            g = np.where(t < 0.5,  68 + (191 -  68) * t2,  191 + (217 - 191) * t2h)
            b = np.where(t < 0.5,  68 + ( 36 -  68) * t2,   36 + (122 -  36) * t2h)

            df_year['color_r'] = r.astype(int)
            df_year['color_g'] = g.astype(int)
            df_year['color_b'] = b.astype(int)
            df_year['elevation'] = 0  # Choropleth fill is primary
        elif indicator == "fertility_rate":
            df_year['raw_value'] = df_year['fertility_rate']
            t = ((df_year['fertility_rate'].clip(1, 7) - 1) / 6).values

            # 3-stop gradient: electric cyan -> deep violet -> vivid magenta
            # Stop 0 (t=0.0): #06c8f0  (  6, 200, 240) -- electric cyan (low fertility)
            # Stop 1 (t=0.5): #8b3ff5  (139,  63, 245) -- deep violet
            # Stop 2 (t=1.0): #f024a0  (240,  36, 160) -- vivid magenta (high fertility)
            t2  = np.clip(t * 2, 0, 1)
            t2h = np.clip((t - 0.5) * 2, 0, 1)

            r = np.where(t < 0.5,   6 + (139 -   6) * t2,  139 + (240 - 139) * t2h)
            g = np.where(t < 0.5, 200 + ( 63 - 200) * t2,   63 + ( 36 -  63) * t2h)
            b = np.where(t < 0.5, 240 + (245 - 240) * t2,  245 + (160 - 245) * t2h)

            df_year['color_r'] = r.astype(int)
            df_year['color_g'] = g.astype(int)
            df_year['color_b'] = b.astype(int)
            df_year['elevation'] = 0
        else:
            df_year['raw_value'] = df_year['net_migration']
            # Log-scale so moderate values are still clearly visible
            mag = df_year['net_migration'].abs()
            intensity = np.log1p(mag) / np.log1p(100000)
            intensity = np.clip(intensity, 0, 1).values
            sign = np.sign(df_year['net_migration']).values

            # Base (near-zero): dark navy-slate [22, 32, 52]
            # Outflow (negative): vivid crimson  [240, 40, 60]
            # Inflow  (positive): electric cyan  [0, 210, 255]
            r = np.where(sign < 0, 22 + (240 - 22) * intensity, 22 + (  0 - 22) * intensity)
            g = np.where(sign < 0, 32 + ( 40 - 32) * intensity, 32 + (210 - 32) * intensity)
            b = np.where(sign < 0, 52 + ( 60 - 52) * intensity, 52 + (255 - 52) * intensity)

            df_year['color_r'] = r.astype(int)
            df_year['color_g'] = g.astype(int)
            df_year['color_b'] = b.astype(int)
            df_year['elevation'] = 0

        payload = df_year[['country', 'iso_alpha', 'longitude', 'latitude', 'elevation', 'color_r', 'color_g', 'color_b', 'pop', 'raw_value']].to_dict(orient="records")
        await session.send_custom_message("update_deck_data", {"data": payload, "indicator": indicator})

    @render_widget
    def population_pyramid():
        year = input.timeline_year()
        df_year = df_full[df_full['year'] == year]
        top_10 = df_year.nlargest(10, 'pop')
        fig = px.bar(top_10, x='pop', y='country', orientation='h', title=f"Top 10 Populations in {year}")
        fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        return fig

    @render_widget
    def historical_trend():
        indicator = input.indicator()
        if indicator == "life_expectancy":
            col = "lifeExp"
        elif indicator == "fertility_rate":
            col = "fertility_rate"
        else:
            col = "net_migration"
            
        global_trend = df_full.groupby('year')[col].mean().reset_index()
        fig = px.line(global_trend, x='year', y=col, title=f"Global Average {indicator}")
        
        year = input.timeline_year()
        fig.add_vline(x=year, line_width=3, line_dash="dash", line_color="red")
        fig.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        return fig

app = App(app_ui, server)