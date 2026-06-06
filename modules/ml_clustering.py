"""
ML module — K-Means clustering, similarity, and simple forecasting.
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.linear_model import LinearRegression
from functools import lru_cache

from .data_loader import load_master_dataset, get_country_list

# Features used for clustering
CLUSTER_FEATURES = [
    'Fertility rate',
    'Life expectancy',
    'Median age',
    'Population growth rate',
    'Elderly share (%)',
    'Children share (%)',
    'Young dependency ratio',
    'Age dependency ratio, old (% of working-age population)',
]

CLUSTER_LABELS = {
    0: 'Aging societies',
    1: 'Rapid-growth populations',
    2: 'Transitional countries',
    3: 'Young populations',
    # Labels get remapped after fitting based on centroids
}


def _get_feature_matrix(year: int = 2023) -> tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    """Build feature matrix for a given year, dropping rows with too many NaNs."""
    df = load_master_dataset()
    df_year = df[df['Year'] == year].copy()

    # Keep only actual countries (ISO codes)
    has_code = df_year['Code'].notna()
    df_year = df_year[has_code].copy()
    df_year = df_year[
        ~df_year['Code'].str.startswith('OWID')
        & (df_year['Code'].str.len() == 3)
    ]

    # Drop rows where key features are missing
    available = [f for f in CLUSTER_FEATURES if f in df_year.columns]
    df_year = df_year.dropna(subset=available, how='any')

    X = df_year[available].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return df_year[['Entity', 'Code'] + available], X_scaled, scaler


@lru_cache(maxsize=128)
def run_clustering(n_clusters: int = 4, year: int = 2023) -> pd.DataFrame:
    """
    Run K-Means clustering on demographic features.
    Returns DataFrame with Entity, Code, Cluster, and PCA coords.
    """
    info_df, X_scaled, scaler = _get_feature_matrix(year)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)

    # PCA for 2D visualization
    pca = PCA(n_components=2, random_state=42)
    pca_coords = pca.fit_transform(X_scaled)

    result = info_df.copy()
    result['Cluster'] = clusters
    result['PCA_x'] = pca_coords[:, 0]
    result['PCA_y'] = pca_coords[:, 1]

    # Auto-label clusters based on median age centroid
    centroids = kmeans.cluster_centers_
    median_age_idx = CLUSTER_FEATURES.index('Median age')
    fertility_idx = CLUSTER_FEATURES.index('Fertility rate')
    growth_idx = CLUSTER_FEATURES.index('Population growth rate')

    # Rank clusters by median age (high → aging, low → young)
    cluster_median_ages = centroids[:, median_age_idx]
    cluster_fertility = centroids[:, fertility_idx]
    cluster_growth = centroids[:, growth_idx]

    # Assign labels
    ranked = np.argsort(cluster_median_ages)[::-1]  # descending
    label_map = {}
    for i, cid in enumerate(ranked):
        if i == 0:
            label_map[cid] = 'Aging low-fertility societies'
        elif i == n_clusters - 1:
            label_map[cid] = 'Young high-fertility populations'
        elif cluster_growth[cid] > 0:
            label_map[cid] = 'Growing transitional countries'
        else:
            label_map[cid] = 'Slow-growth transitional countries'

    result['Cluster Label'] = result['Cluster'].map(label_map)

    return result


@lru_cache(maxsize=512)
def get_similar_countries(country: str, top_n: int = 5, year: int = 2023) -> pd.DataFrame:
    """
    Return the top-N most demographically similar countries using cosine similarity.
    """
    info_df, X_scaled, _ = _get_feature_matrix(year)

    # Find the country index (use iloc position)
    matches = info_df[info_df['Entity'] == country]
    if len(matches) == 0:
        return pd.DataFrame()
    pos = matches.index[0]
    # Convert to position in the filtered dataframe
    arr_pos = info_df.index.get_loc(pos)

    # Cosine similarity
    sims = cosine_similarity([X_scaled[arr_pos]], X_scaled)[0]

    results = info_df.copy()
    results = results.reset_index(drop=True)
    results['Similarity'] = sims
    results = results[results['Entity'] != country].sort_values('Similarity', ascending=False)
    return results.head(top_n)[['Entity', 'Code', 'Similarity']]


@lru_cache(maxsize=1024)
def forecast_indicator(country: str, indicator: str, forecast_years: int = 15) -> dict:
    """
    Simple linear regression forecast for a given country + indicator.
    Uses the last 30 years of data.
    Returns dict with historical years, historical values, forecast years, forecast values.
    """
    df = load_master_dataset()
    cdf = df[(df['Entity'] == country) & (df['Year'] >= 1994)].dropna(subset=[indicator])

    if len(cdf) < 10:
        return {'error': f'Not enough data for {country} - {indicator}'}

    X_hist = cdf[['Year']].values
    y_hist = cdf[indicator].values

    model = LinearRegression()
    model.fit(X_hist, y_hist)

    last_year = cdf['Year'].max()
    future_years = np.arange(last_year + 1, last_year + forecast_years + 1).reshape(-1, 1)
    forecast = model.predict(future_years)

    return {
        'country': country,
        'indicator': indicator,
        'historical_years': X_hist.flatten().tolist(),
        'historical_values': y_hist.tolist(),
        'forecast_years': future_years.flatten().tolist(),
        'forecast_values': forecast.tolist(),
        'trend_coef': float(model.coef_[0]),
        'r2_score': float(model.score(X_hist, y_hist)),
    }


@lru_cache(maxsize=512)
def get_demographic_profile(country: str, year: int = 2023) -> dict:
    """Get a summary demographic profile for a single country."""
    df = load_master_dataset()
    row = df[(df['Entity'] == country) & (df['Year'] == year)]

    if row.empty:
        return {'error': f'No data for {country} in {year}'}

    row = row.iloc[0]
    cluster_df = run_clustering()
    cluster_info = cluster_df[cluster_df['Entity'] == country]

    indicators = [
        ('Population', '{:,.0f}'),
        ('Fertility rate', '{:.1f}'),
        ('Life expectancy', '{:.1f}'),
        ('Median age', '{:.1f}'),
        ('Population growth rate', '{:.2f}%'),
        ('Elderly share (%)', '{:.1f}%'),
        ('Children share (%)', '{:.1f}%'),
        ('Young dependency ratio', '{:.1f}'),
    ]

    profile = {'Country': country, 'Year': year}
    for ind, fmt in indicators:
        if ind in df.columns:
            val = row[ind]
            profile[ind] = fmt.format(val) if not pd.isna(val) else 'N/A'

    if not cluster_info.empty:
        profile['Cluster'] = cluster_info.iloc[0]['Cluster Label']

    similar = get_similar_countries(country)
    profile['Similar countries'] = similar['Entity'].tolist()

    return profile


if __name__ == "__main__":
    print("=== K-Means Clustering ===")
    clusters = run_clustering()
    print(clusters['Cluster Label'].value_counts())
    print(clusters.head())

    print("\n=== Similar to Japan ===")
    print(get_similar_countries('Japan'))

    print("\n=== Similar to Vietnam ===")
    print(get_similar_countries('Vietnam'))

    print("\n=== Forecast: Japan Median age ===")
    print(forecast_indicator('Japan', 'Median age'))

    print("\n=== Vietnam Profile ===")
    print(get_demographic_profile('Vietnam'))
