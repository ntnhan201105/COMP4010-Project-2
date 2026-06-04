import pandas as pd
import numpy as np
import plotly.express as px

print('Loading gapminder data as a base...')
df = px.data.gapminder()

# Expand years to 1950-2026 by interpolating
countries = df['country'].unique()
all_years = list(range(1950, 2027))
grid = pd.MultiIndex.from_product([countries, all_years], names=['country', 'year']).to_frame(index=False)

df_full = pd.merge(grid, df, on=['country', 'year'], how='left')
df_full = df_full.sort_values(['country', 'year'])

# Forward and backward fill missing years per country
def ffill_bfill(group):
    group[['continent', 'iso_alpha', 'iso_num']] = group[['continent', 'iso_alpha', 'iso_num']].ffill().bfill()
    group[['lifeExp', 'pop', 'gdpPercap']] = group[['lifeExp', 'pop', 'gdpPercap']].interpolate(method='linear', limit_direction='both')
    return group

df_full = df_full.groupby('country', group_keys=False).apply(ffill_bfill)

# Generate mock data for the other indicators
np.random.seed(42)

def generate_fertility(row):
    # Base fertility decreases over time
    base = 6.0 - ((row['year'] - 1950) / 76) * 4.0
    # Add some noise
    return max(0.5, base + np.random.normal(0, 0.5))

def generate_migration(row):
    # Migration scaled by pop
    return np.random.normal(0, 0.005) * row['pop']

df_full['fertility_rate'] = df_full.apply(generate_fertility, axis=1)
df_full['net_migration'] = df_full.apply(generate_migration, axis=1)

# Generate pseudo-realistic lat/lon coordinates
# In a real app we join this with a country centroids dataset
print('Assigning lat/lon coordinates...')
np.random.seed(100)
country_coords = {}
for c in countries:
    country_coords[c] = {
        'latitude': np.random.uniform(-50, 60),
        'longitude': np.random.uniform(-100, 100)
    }

df_full['latitude'] = df_full['country'].map(lambda x: country_coords[x]['latitude'])
df_full['longitude'] = df_full['country'].map(lambda x: country_coords[x]['longitude'])

print('Saving processed data to parquet...')
df_full.to_parquet('data/demographics.parquet')
print('Done!')
