# Instructions for Copilot: Building R Shiny/Python Shiny Demographic Dashboards

## Rubrics
### 2b. Application

| # | Criterion | Weight | Excellent | Good | Satisfactory | Needs Improvement |
|---|-----------|:------:|-----------|------|--------------|-------------------|
| 2.6 | **Visualization quality & design** | 6% | Polished, aesthetic, effective charts; strong visual storytelling | Good charts, with clear design | Basic charts, with limited polish | Cluttered or ineffective |
| 2.7 | **Chart requirements met** | 3% | ≥5 charts and ≥3 chart types, all purposeful | Meets the minimums | Just below the minimums | Well below the minimums |
| 2.8 | **Interactivity** | 6% | Rich, meaningful interaction (filtering, brushing, cross-filtering, linked views, tooltips) that aids understanding | Good, working interactivity | Basic filtering only | Static or broken interaction |
| 2.9 | **Technical complexity** | 5% | Advanced techniques and a robust data pipeline; goes well beyond a basic dashboard | Solid complexity | Modest complexity | Minimal complexity |
| 2.10 | **ML / analytics** | 6% | Forecasting, spatial, or predictive model meaningfully embedded in the visual analytics workflow | ML present and relevant | ML present, but shallow or disconnected | Absent where expected |
| 2.11 | **Proper use of Python Shiny** | 4% | Idiomatic reactive programming; appropriate inputs, outputs, layouts, and modules; efficient reactivity with no redundant recomputation | Mostly idiomatic, with minor anti-patterns | Works, but misuses reactivity or fights the framework | Improper or broken Shiny usage |


## Objective
Build two highly interactive narrative-driven dashboards within a Python Shiny application. The code must maximize a grading rubric emphasizing polished visualizations, rich cross-filtering/interactivity, advanced analytics (ML forecasting & clustering), and idiomatic, efficient reactive programming (no redundant recomputations).

---

## Global Architecture & Performance Guidelines
1. **Idiomatic Reactivity:** Use `reactive.calc` to perform all data filtering, forecasting, and clustering *once* per user interaction. Individual chart render outputs must watch these single reactive calculations to prevent redundant execution.
2. **Interactive Brushing/Linking:** Clicking or brushing data points in one chart must dynamically update the metrics, years, and structures of the other charts.

---

## Dashboard 1: The Refugee Crisis & Geopolitical Shockwaves
* **Core Narrative:** Capturing the massive regional and global displacement ripple effects caused by conflict.
* **Target Countries of Interest:** * Out-Migration: **Syria**
  * In-Migration (Neighbors): **Turkey**, **Lebanon**, **Jordan**
  * In-Migration (Long-Distance): **Germany**
  * Historical Contrast Group: **Poland**, **Ukraine** (Captures the sudden post-2022 migration pivot).

### Visual Layout & Figure Implementation Details:
* **Figure 1: Multi-Line Time-Series Chart (Plotly or Plotnine)**
  * *Data:* Net Migration Rate on Y-axis, Year on X-axis (1990 to 2022).
  * *Functionality:* Displays a unified view of all 7 target countries. Ensure a clear baseline at 0. Brushing a specific year range on this chart updates the rest of the dashboard.
* **Figure 2: Linked Bar Chart (Per Capita Burden)**
  * *Data:* Refugees/displaced persons hosted *per 1,000 native inhabitants* for the selected year.
  * *Functionality:* Highlights the intense socioeconomic strain on small border nations like Lebanon and Jordan compared to larger European states.
* **Figure 3: Dynamic Population Structure Bar Chart (Age-Only)**
  * *Data:* Age groups on the Y-axis (or X-axis), population count/percentage on the other. No sex breakdown.
  * *Functionality:* Changes dynamically based on the selected country and year. Shows the "hollowing out" of working-age or youth brackets in conflict zones vs. their growth in receiving states.
* **Figure 4: Advanced ML Forecast Line Chart (Time-Series + Ribbon)**
  * *Analytics:* Fit an interactive time-series forecasting model (e.g., ARIMA or Exponential Smoothing via `statsmodels`) using historical data up to 2022.
  * *Output:* Generate and visualize predictions for the next 17 years (**2023 to 2040**). Plot the historical line, the forecasted mean line, and a semi-transparent confidence interval ribbon. Allow the user to tweak forecast parameters via UI inputs if possible.

---

## Dashboard 2: The Ultra-Low Fertility Cliff
* **Core Narrative:** Tracking the severe, systemic economic and social shrinkage across East Asia contrasted against high-growth nations.
* **Target Countries of Interest:**
  * The Collapse Group: **South Korea**, **Taiwan**, **Japan**
  * The Scale Shift: **China**
  * The High-Fertility Contrast Group (3 Countries): **Niger**, **Chad**, **Mali** (Visually frames the extreme opposite of the demographic spectrum).

### Visual Layout & Figure Implementation Details:
* **Figure 1: Dual-Axis Multi-Line Chart**
  * *Data:* Total Fertility Rate (TFR) over time. 
  * *Functionality:* Include a prominent, static dashed reference horizontal line at exactly **2.1** (Demographic Replacement Level). This clearly separates the African continent context from East Asia sinking deep below the line.
* **Figure 2: Interactive Population Structure Bar Chart (Age-Only)**
  * *Data:* Age brackets (e.g., 0-14, 15-64, 65+ or finer groups). No sex breakdown available.
  * *Functionality:* As the user toggles from 1990 to the present, this chart must visually transform. For East Asian nations, it must morph from a traditional bottom-heavy pyramid into a top-heavy "inverted" block, signaling massive upcoming elder-dependency ratios.
* **Figure 3: Socioeconomic Scatter Plot with Trend Lines**
  * *Data:* X-axis: Independent development/economic metrics (e.g., Urbanization Rate or Female Labor Force Participation); Y-axis: Fertility Rate.
  * *Functionality:* Draws global correlation lines helping the user deduce *why* urbanized, highly competitive structures crush birth rates.
* **Figure 4: Advanced ML K-Means Clustering Dashboard Component**
  * *Analytics:* Use `scikit-learn` to run a real-time K-Means clustering algorithm on the global dataset based on demographic features (e.g., TFR, Median Age, Growth Rate).
  * *Output:* A 2D scatter plot (or PCA projection) mapping global nations. East Asian nations should visibly separate into a distinct, isolated "Demographic Winter" cluster. Provide a UI slider to let users change the cluster count ($K$) dynamically, instantly updating the plot.

---

## Prompt Template for Copying into Copilot Chat:
"Using the constraints, data logic, and architectural rules specified in the markdown above, write clean, production-grade Python Shiny code implementing these two specific dashboard layouts. Ensure code comments explicitly detail the reactive data paths (`reactive.calc`) to prove there is no redundant re-computation of charts."