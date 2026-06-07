# GlobeVis

## Where People Move, Where Populations Fade

GlobeVis is an interactive Python Shiny dashboard that turns global demographic data into a visual story about two major demographic forces: migration pressure and fertility decline. The project combines a deck.gl 3D globe, linked Plotly story dashboards, country deep dives, and exploratory analytics/ML to help users understand where people move, where host regions absorb pressure, and where populations are fading below replacement fertility.

The dashboard was built for COMP4010 Project 2: Data Stories - Building Interactive Dashboards with Python Shiny.

Live demo: `[ADD LIVE DEMO LINK HERE]`  
Repository: `https://github.com/ntnhan201105/COMP4010-Project-2`

## Project Overview

### Problem Statement

Global demographic data is large, multi-dimensional, and difficult to interpret from static tables alone. Migration, fertility, ageing, and mortality trends unfold across both geography and time. GlobeVis addresses this by using an interactive globe as the spatial anchor and linked story dashboards as the analytical layer.

### Motivation

The project focuses on two demographic stories that are visible in the data and meaningful for public understanding:

- Migration pressure: conflict and economic collapse can push people out of origin countries while nearby host countries absorb sudden demographic pressure.
- Fertility decline: several East Asian societies have fallen far below the 2.1 replacement level, creating long-run population ageing concerns.

### Target Users

GlobeVis is designed for students, journalists, and policy-curious readers who need to understand global demographic patterns quickly without reading raw demographic tables.

### Core Dashboard Questions

- Where do migration outflows and inflows appear most strongly?
- How do displacement shocks show up in country-level net migration rates?
- Which host countries absorb regional migration pressure?
- Which countries have fallen below replacement fertility?
- How is low fertility connected to population ageing and development proxies?
- What do simple exploratory forecasts suggest, and where should users be cautious?

## Data Sources

### Our World in Data

The main demographic indicators come from Our World in Data (OWID) exports based on the United Nations World Population Prospects 2024. OWID provides country-year indicator files used to build the merged demographic table.

### United Nations World Population Prospects 2024

UN World Population Prospects 2024 is the underlying population source for the OWID demographic indicators. It contributes demographic estimates such as population, fertility, mortality, migration, growth, and age structure.

### Natural Earth

Natural Earth country geometry is used by the browser-side deck.gl globe and 2D map layer. Country polygons are joined to demographic records through ISO-3 country codes where possible.

## Dataset and Preprocessing

The preprocessing pipeline merges multiple OWID indicator exports into one country-year table. The root merge output is stored in `data/merged_demographics.csv`, and the Shiny app consumes the optimized artifact `globevis/data/demographics.parquet`.

### Raw Indicators

The project uses OWID demographic exports covering:

- Population
- Annual population change
- Annual net migration rate
- Birth rate
- Child mortality rate
- Death rate
- Fertility rate
- Infant mortality rate
- Life expectancy at birth
- Natural population growth rate
- Population by broad age group
- Population density
- Population growth rate

The `datasets/` directory also includes metadata and readme files for the raw OWID exports. The duplicate `age-structure` source is kept in the repository but skipped during the merge because it semantically overlaps with `population-by-age-group`.

### Merge Key and Output

All indicator files are merged on:

```text
(Entity, Code, Year)
```

The current merge report records:

| Property | Value |
| --- | --- |
| Output rows | 19,388 |
| Output columns | 20 |
| Grain | One row per Entity, Code, Year |
| Historical year range | 1950-2023 |
| Entities | 262 |
| Rows with missing Code | 592 |
| Forecast layer in app | 2024-2030 |
| Main app artifact | `globevis/data/demographics.parquet` |
| Narrative artifact | `globevis/data/historical_events.json` |

### Validation Checks

The preprocessing code performs several checks:

- Enforces one-to-one merge validation for every source.
- Checks for duplicate keys in source files.
- Checks for duplicate keys after merge.
- Skips duplicate semantic datasets when a canonical source is available.
- Reports age-band consistency gaps against total population.
- Separates real countries from aggregate entities where the app requires country-level maps.

### Cleaning Steps

- Standardizes country-year indicator columns after merge.
- Keeps ISO-3 codes for map joins where available.
- Filters country-level rows for globe rendering.
- Converts the app-facing data to Parquet for faster startup and lower memory overhead.
- Builds `historical_events.json` to provide narrative context for selected country deep dives.
- Generates exploratory forecast rows through 2030 for supported indicators.

### Known Data Limitations

- Net migration rate is a country-level indicator, not a bilateral refugee-flow dataset.
- The migration story uses known displacement corridors as narrative overlays, while charts use country-level OWID net migration rates.
- Some entities are aggregates or have missing ISO codes and cannot be mapped cleanly.
- Broad age bands simplify the age-structure story and may hide within-band variation.
- Natural Earth polygons and OWID ISO codes do not always align perfectly.
- Forecast values are exploratory and should not be interpreted as official demographic projections.

## Dashboard Design

GlobeVis follows a "one globe + many lenses + two deep stories" design.

### One Globe

The central view is a deck.gl globe. It provides spatial context first, then lets the user open story dashboards without leaving the map. The globe supports auto-rotation, pause-on-interaction, fly-to camera movements, back-face culling, custom tooltips, and a 2D map toggle.

### Many Lenses

The globe can be recolored through five indicator lenses:

- Migration Rate
- Fertility Rate
- Life Expectancy
- Child Mortality
- Death Rate

The map legends and dashboard encodings use a colorblind-friendly palette. The design avoids relying only on red-green contrasts by combining warm orange, blue, gray, line style, marker shape, and chart labels.

### Migration Story

The migration story focuses on displacement pressure and regional hosting:

- Syria and Venezuela are treated as origin cases.
- Turkey, Lebanon, Jordan, Colombia, and Peru are treated as host or regional counterpart countries.
- The dashboard connects net migration shock lines, host pressure bars, age-structure shifts, and a migration forecast panel.

### Fertility Story

The fertility story focuses on countries far below replacement fertility and high-fertility contrasts:

- South Korea, Taiwan, Japan, and China anchor the low-fertility side.
- Niger, Chad, and Mali provide high-fertility contrast cases.
- The dashboard connects fertility trend lines, age-structure comparisons, fertility-vs-development proxies, and K-Means/PCA cluster views.

### Country Deep Dive

Clicking a country opens a deep-dive panel with:

- Country name and selected indicator.
- Current year value.
- A compact trend chart with historical and projected segments when enabled.
- Narrative context from `historical_events.json` when available.

## Visualizations

The dashboard includes more than five major visualizations and more than three chart types.

| Visualization | Type | Purpose |
| --- | --- | --- |
| 3D globe choropleth | deck.gl globe map | Shows geographic distribution of the selected indicator over time. |
| Indicator lens map | Choropleth | Lets users compare migration, fertility, life expectancy, child mortality, and death rate. |
| Migration net-rate lines | Multi-line chart | Shows how origin and host countries diverge during displacement periods. |
| Peak historical immigration pressure | Horizontal bar chart | Summarizes strongest positive host-pressure proxy values in the selected migration window. |
| Migration age-structure shift | Grouped horizontal age bars | Compares fixed pre-crisis and peak-exodus windows for Syria and Venezuela corridors. |
| Migration forecast | Line chart with confidence ribbon | Displays exploratory net migration forecast with uncertainty band. |
| Fertility vs replacement | Multi-line chart | Compares country fertility rates against the 2.1 replacement benchmark. |
| Fertility age structure | Grouped horizontal age bars | Shows how low fertility connects to population ageing. |
| Fertility vs development proxy | Scatter plot with trend line | Shows the relationship between fertility and proxies such as density, life expectancy, mortality, or growth. |
| K-Means demographic clusters | PCA scatter plot | Shows statistically separable demographic profiles in two dimensions. |

## Interactivity

Interactivity is used to support the data story rather than simply decorate the interface.

- Year slider: updates the globe, story charts, deep-dive marker, and time-dependent dashboard panels.
- Indicator/lens selection: changes the map encoding and opens the relevant migration or fertility story.
- Country click selection: opens a country deep dive without leaving the globe.
- Story view opening: keeps the globe visible while sliding in linked dashboard charts.
- Brush window in migration story: lets users focus the host-pressure calculation on a selected migration period.
- Country selectors: filter story figures to selected countries and allow additional country comparisons.
- Linked trend markers: selected years and crisis windows are annotated or shaded in line charts.
- Synchronized age comparisons: migration age-structure charts use fixed crisis windows, while fertility age charts update by selected story country and year.
- Scatter frame controls: users can change the x-axis development proxy for the fertility scatter.
- Theme synchronization: dark/light mode updates the Shiny UI, Plotly charts, deck.gl tooltip styling, and dashboard CSS variables.

These interactions help users connect spatial context, temporal change, and analytical summaries in one workflow.

## ML and Analytics

Analytics is embedded into the visual workflow. The goal is not to produce production-grade demographic forecasts, but to help users reason about uncertainty, clusters, and broad directional patterns.

### Linear Regression Projections

Country-indicator projections extend supported demographic indicators to 2030. The app trains simple recent-trend linear models, especially on recent historical years such as 2009-2023 where available. Projection outputs are clamped to realistic demographic ranges, for example non-negative population values and bounded fertility or mortality rates.

Where it appears:

- The optional "Show ML projections to 2030" control.
- Dashed projected segments in story trend charts.
- Projected fertility ranking panels.
- Deep-dive trend charts when projections are enabled.

### Holt-Winters Exponential Smoothing

The migration forecast panel uses Holt-Winters exponential smoothing for selected country net migration rate forecasts to 2030. It displays a widening 95% uncertainty band. If `statsmodels` or the smoothing fit is unavailable, the app falls back to a linear fit.

Where it appears:

- Migration story forecast chart.

### K-Means Clustering

The fertility story uses K-Means to segment countries by demographic profile. The feature set includes nine standardized demographic features such as fertility, life expectancy, population growth, birth/death rates, child share, working-age share, and elder share.

Where it appears:

- Fertility K-Means Demographic Clusters chart.

### PCA

PCA projects the standardized clustering feature space into two dimensions for visual interpretation.

Where it appears:

- The x/y coordinates of the K-Means cluster scatter plot.

### Log-Linear OLS Trend

The fertility-vs-development proxy scatter adds a simple OLS trend line. For population density, the fit uses a log-transformed x-axis because density is highly skewed.

Where it appears:

- Fertility vs Development Proxy chart.

### NumPy Fallbacks

NumPy-based fitting provides lightweight backup behavior if optional modeling packages or precomputed outputs are unavailable.

### ML Limitations

The ML layer is exploratory and interpretive. It is not a validated production forecasting system. Current limitations include:

- No formal held-out validation set.
- No complete error metric reporting in the dashboard.
- Simple models may underfit structural breaks such as wars, hyperinflation, pandemics, or policy changes.
- Forecast bands communicate uncertainty qualitatively, but they should not be read as official prediction intervals.

## Technical Architecture

### Python Shiny Server

`globevis/app.py` is the main Python Shiny app. Shiny reactive programming manages user inputs, selected story state, year updates, chart filters, and data subsets.

### Data Artifacts

At startup, the server loads:

```text
globevis/data/demographics.parquet
globevis/data/historical_events.json
```

The app precomputes color payloads by year and indicator so that globe updates are fast during slider movement. Shared reactive calculations reduce redundant filtering and recomputation across charts.

### Browser-Side deck.gl Globe

`globevis/www/deck_map.js` renders the 3D globe and 2D map. It handles:

- deck.gl globe and map views.
- GeoJSON country polygons from Natural Earth.
- Custom DOM tooltips.
- Auto-rotation and pause-on-interaction.
- Fly-to story transitions.
- Country click messages back to Shiny.
- Group focus behavior for story dashboards.

### Plotly Chart Layer

Plotly is used for the linked story charts, deep-dive trend chart, bars, scatter plots, forecast ribbons, and PCA cluster views. Chart colors, hover labels, and layout are synchronized with the app theme.

### JavaScript-Shiny Bridge

Custom Shiny messages connect the Python server and browser-side JavaScript:

- The server sends year/indicator color payloads to the globe.
- The server sends group focus state when a story opens.
- JavaScript sends country click events back to Shiny.
- Client-side resize observers resize existing Plotly charts when the dashboard expands or collapses.

### CSS and Theme System

`globevis/www/style.css` and `globevis/www/deep_dive.css` define the dashboard layout, dark/light theme variables, story panel transitions, and chart control styling.

### Offline Pipeline

The offline pipeline performs merge, validation, cleaning, forecast generation, and artifact export. The key scripts are:

- `scripts/merge_datasets.py`
- `globevis/process_data.py`
- `globevis/generate_history.py`
- `globevis/predict_future.py`

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ntnhan201105/COMP4010-Project-2.git
cd COMP4010-Project-2
```

### 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r globevis/requirements.txt
```

The main dependencies include Python Shiny, shinywidgets, pydeck, Plotly, pandas, NumPy, pyarrow, scikit-learn, and statsmodels.

## How to Run Locally

The generic Shiny command format is:

```bash
shiny run globevis/app.py
```

For this repository, the recommended command is to run from inside `globevis/`, because `app.py` currently loads `./data/demographics.parquet` relative to the app directory:

```bash
cd globevis
python -m shiny run --host 127.0.0.1 --port 8000 app.py
```

Then open:

```text
http://127.0.0.1:8000
```

### Troubleshooting

Missing packages:

```bash
pip install -r globevis/requirements.txt
```

Missing app data files:

- Confirm `globevis/data/demographics.parquet` exists.
- Confirm `globevis/data/historical_events.json` exists.
- If missing, rerun preprocessing scripts if the raw datasets are available.

Wrong working directory:

- If the app cannot find `./data/demographics.parquet`, run it from the `globevis/` directory.

Parquet engine issues:

```bash
pip install pyarrow
```

Port already in use:

```bash
python -m shiny run --host 127.0.0.1 --port 8001 app.py
```

Browser does not show updated JavaScript/CSS:

- Hard refresh the browser.
- Add a query string such as `?v=reload`.

## Deployment

The intended deployment target is shinyapps.io.

Live deployment placeholder:

```text
[ADD LIVE DEMO LINK HERE]
```

Deployment notes:

- Ensure `globevis/data/demographics.parquet` and `globevis/data/historical_events.json` are included with the deployed app.
- Ensure `globevis/www/` assets are included.
- Install dependencies from `globevis/requirements.txt`.
- Confirm that the deployment environment supports `pyarrow`, `scikit-learn`, and `statsmodels`, or that fallback behavior is acceptable.

## Reproducibility

A grader should be able to reproduce the app from a clean clone if the repository includes the raw dataset folders and processed app artifacts.

### Run With Included Artifacts

```bash
git clone https://github.com/ntnhan201105/COMP4010-Project-2.git
cd COMP4010-Project-2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r globevis/requirements.txt
cd globevis
python -m shiny run --host 127.0.0.1 --port 8000 app.py
```

### Regenerate Processed Data

If raw OWID exports are available in `datasets/`, the processed artifacts can be regenerated with:

```bash
python scripts/merge_datasets.py
cd globevis
python process_data.py
python generate_history.py
python predict_future.py
python -m shiny run --host 127.0.0.1 --port 8000 app.py
```

Notes:

- The merge step writes `data/merged_demographics.csv` and `data/merge_report.txt`.
- The app step uses `globevis/data/demographics.parquet`.
- `historical_events.json` is a narrative support artifact, not a primary demographic dataset.
- K-Means uses a fixed random seed in the app for stable cluster labels.
- Full reproducibility depends on the availability and version consistency of the raw OWID export files.

## Repository Organization

```text
COMP4010-Project-2/
|-- README.md
|-- project_2_rubric.md
|-- CLAUDE.md
|-- data/
|   |-- merged_demographics.csv
|   |-- merge_report.txt
|-- datasets/
|   |-- annual-net-migration-rate/
|   |-- birth-rate/
|   |-- child-mortality-rate/
|   |-- death-rate/
|   |-- fertility-rate/
|   |-- infant-mortality-rate/
|   |-- life-expectancy-at-birth/
|   |-- natural-population-growth-rate/
|   |-- population/
|   |-- population-by-age-group/
|   |-- population-density/
|   |-- population-growth-rate/
|   |-- annual-change-in-population/
|-- scripts/
|   |-- merge_datasets.py
|-- globevis/
|   |-- app.py
|   |-- process_data.py
|   |-- generate_history.py
|   |-- predict_future.py
|   |-- requirements.txt
|   |-- Implementation_Plan.md
|   |-- DASHBOARD_OVERVIEW.md
|   |-- data/
|   |   |-- demographics.parquet
|   |   |-- historical_events.json
|   |-- www/
|   |   |-- deck_map.js
|   |   |-- style.css
|   |   |-- deep_dive.css
|   |   |-- scroll_observer.js
|-- report/
|   |-- main.tex
|   |-- main.pdf
```

## Team Contributions

| Team Member | Contributions |
| --- | --- |
| Nguyen Tien Nhan | Project management and coordination; project ideation and story design; quality assurance and testing; deployment support; presentation delivery. |
| Hoang Anh Minh | Development of the interactive 3D globe and 2D map visualizations; frontend visualization implementation; presentation delivery. |
| Pham Tuan Hung | Development of the Migration dashboard and associated visual analytics; report writing and documentation. |
| Do Quang Thai An | Development of the Fertility dashboard and associated visual analytics; slide design and preparation for presentation. |

These descriptions should be supported by commit history and final presentation materials where possible.

## Key Findings

- Displacement redistributes regionally. Syria and Venezuela illustrate how origin shocks can coincide with pressure absorbed by nearby host countries.
- East Asia has fallen far below the 2.1 replacement fertility level, especially in South Korea, Taiwan, Japan, and China.
- Low fertility is linked to population ageing, visible through age-structure comparisons and long-run fertility trends.
- Demographic profiles are statistically separable through K-Means clustering and PCA projection.
- Development proxies generally track fertility decline, but meaningful outliers remain.
- Forecasts suggest persistent demographic pressure, but they should be interpreted with uncertainty rather than treated as definitive predictions.

## Challenges and Lessons Learned

- Harmonizing many OWID CSV files required careful key validation and duplicate checks.
- Separating real countries from aggregate entities was necessary for map-based visualization.
- Matching ISO-3 codes to Natural Earth polygons required careful handling of missing and non-country codes.
- Age-band mismatch issues required validation against total population.
- Building a smooth browser-side 3D globe required client-side optimization, custom tooltips, and interaction handling.
- Avoiding redundant Shiny recomputation required shared reactive calculations and precomputed color payloads.
- Deployment requires graceful degradation when optional analytics dependencies are unavailable.
- Proxy indicators and exploratory forecasts must be communicated honestly to avoid overclaiming.

## Future Work

- Final shinyapps.io deployment.
- Forecast validation with holdout backtesting and error metrics.
- Richer covariate models for migration and fertility projections.
- More scrollytelling to guide first-time users through the two stories.
- More cross-filtering between globe selections, story charts, and country panels.
- Subnational or bilateral migration data for more precise flow analysis.
- User testing with students, journalists, and policy-curious readers.

## License and Acknowledgements

This project uses public demographic data and open-source visualization tools. Please review the original data licenses before redistribution.

Acknowledgements:

- Our World in Data for demographic indicator exports and documentation.
- United Nations World Population Prospects 2024 for the underlying demographic estimates.
- Natural Earth for country geometry data.
- Python Shiny for the reactive dashboard framework.
- deck.gl for the browser-side 3D globe and map rendering.
- Plotly for linked interactive charts.
- pandas, NumPy, pyarrow, scikit-learn, and statsmodels for data processing and exploratory analytics.

The project team is responsible for the dashboard design, preprocessing workflow, visual storytelling, and interpretation. Any errors in analysis or presentation are our own.
