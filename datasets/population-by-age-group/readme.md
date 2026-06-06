# Population by age group - Data package

This data package contains the data that powers the chart ["Population by age group"](https://ourworldindata.org/explorers/population-and-demography?indicator=Population+by+age+group&Sex=Both+sexes&Age=Total&Projection+scenario=None&country=CHN~IND~USA~IDN~PAK~NGA~BRA~JPN) on the Our World in Data website.

## CSV Structure

The high level structure of the CSV file is that each row is an observation for an entity (usually a country or region) and a timepoint (usually a year).

The first two columns in the CSV file are "Entity" and "Code". "Entity" is the name of the entity (e.g. "United States"). "Code" is the OWID internal entity code that we use if the entity is a country or region. For most countries, this is the same as the [iso alpha-3](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3) code of the entity (e.g. "USA") - for non-standard countries like historical countries these are custom codes.

The third column is either "Year" or "Day". If the data is annual, this is "Year" and contains only the year as an integer. If the column is "Day", the column contains a date string in the form "YYYY-MM-DD".

The remaining columns are the data columns, each of which is a time series. If the CSV data is downloaded using the "full data" option, then each column corresponds to one time series below. If the CSV data is downloaded using the "only selected data visible in the chart" option then the data columns are transformed depending on the chart type and thus the association with the time series might not be as straightforward.


## Metadata.json structure

The .metadata.json file contains metadata about the data package. The "charts" key contains information to recreate the chart, like the title, subtitle etc.. The "columns" key contains information about each of the columns in the csv, like the unit, timespan covered, citation for the data etc..

## About the data

Our World in Data is almost never the original producer of the data - almost all of the data we use has been compiled by others. If you want to re-use data, it is your responsibility to ensure that you adhere to the sources' license and to credit them correctly. Please note that a single time series may have more than one source - e.g. when we stich together data from different time periods by different producers or when we calculate per capita metrics using population data from a second source.

### How we process data at Our World In Data
All data and visualizations on Our World in Data rely on data sourced from one or several original data providers. Preparing this original data involves several processing steps. Depending on the data, this can include standardizing country names and world region definitions, converting units, calculating derived indicators such as per capita measures, as well as adding or adapting metadata such as the name or the description given to an indicator.
[Read about our data pipeline](https://docs.owid.io/projects/etl/)

## Detailed information about each time series


## Number of children under 5 – UN WPP
The total population, measured on 1 July of the year shown. This only includes people aged 0-4.
Last updated: July 12, 2024  
Date range: 1950–2023  
Unit: people  


### How to cite this data

#### In-line citation
If you have limited space (e.g. in data visualizations), you can use this abbreviated in-line citation:  
UN, World Population Prospects (2024) – processed by Our World in Data

#### Full citation
UN, World Population Prospects (2024) – processed by Our World in Data. “Number of children under 5 – UN WPP” [dataset]. United Nations, “World Population Prospects”; United Nations, “World Population Prospects - Interim Update” [original data].
Source: UN, World Population Prospects (2024) – processed by Our World In Data

### Sources

#### United Nations – World Population Prospects
Retrieved on: 2024-07-11  
Retrieved from: https://population.un.org/wpp/downloads/  

#### United Nations – World Population Prospects - Interim Update
Retrieved on: 2026-03-31  
Retrieved from: https://population.un.org/wpp/downloads/  

#### Notes on our processing step for this indicator
The UN publishes population by single year of age. We aggregate these into the broader age groups shown here (e.g. 0–14, 15–64, 65+, 18+, 15–49). Our continental aggregates (Africa, Asia, Europe, North America, South America, Oceania) are computed by summing across countries, and may differ slightly from regional aggregates the UN publishes directly, which use a different country grouping.


## Number of people aged 65 and over – UN WPP
The total population, measured on 1 July of the year shown. This only includes people aged 65+.
Last updated: July 12, 2024  
Date range: 1950–2023  
Unit: people  


### How to cite this data

#### In-line citation
If you have limited space (e.g. in data visualizations), you can use this abbreviated in-line citation:  
UN, World Population Prospects (2024) – processed by Our World in Data

#### Full citation
UN, World Population Prospects (2024) – processed by Our World in Data. “Number of people aged 65 and over – UN WPP” [dataset]. United Nations, “World Population Prospects”; United Nations, “World Population Prospects - Interim Update” [original data].
Source: UN, World Population Prospects (2024) – processed by Our World In Data

### Sources

#### United Nations – World Population Prospects
Retrieved on: 2024-07-11  
Retrieved from: https://population.un.org/wpp/downloads/  

#### United Nations – World Population Prospects - Interim Update
Retrieved on: 2026-03-31  
Retrieved from: https://population.un.org/wpp/downloads/  

#### Notes on our processing step for this indicator
The UN publishes population by single year of age. We aggregate these into the broader age groups shown here (e.g. 0–14, 15–64, 65+, 18+, 15–49). Our continental aggregates (Africa, Asia, Europe, North America, South America, Oceania) are computed by summing across countries, and may differ slightly from regional aggregates the UN publishes directly, which use a different country grouping.


## Number of people aged 25 to 64 – UN WPP
The total population, measured on 1 July of the year shown. This only includes people aged 25-64.
Last updated: July 12, 2024  
Date range: 1950–2023  
Unit: people  


### How to cite this data

#### In-line citation
If you have limited space (e.g. in data visualizations), you can use this abbreviated in-line citation:  
UN, World Population Prospects (2024) – processed by Our World in Data

#### Full citation
UN, World Population Prospects (2024) – processed by Our World in Data. “Number of people aged 25 to 64 – UN WPP” [dataset]. United Nations, “World Population Prospects”; United Nations, “World Population Prospects - Interim Update” [original data].
Source: UN, World Population Prospects (2024) – processed by Our World In Data

### Sources

#### United Nations – World Population Prospects
Retrieved on: 2024-07-11  
Retrieved from: https://population.un.org/wpp/downloads/  

#### United Nations – World Population Prospects - Interim Update
Retrieved on: 2026-03-31  
Retrieved from: https://population.un.org/wpp/downloads/  

#### Notes on our processing step for this indicator
The UN publishes population by single year of age. We aggregate these into the broader age groups shown here (e.g. 0–14, 15–64, 65+, 18+, 15–49). Our continental aggregates (Africa, Asia, Europe, North America, South America, Oceania) are computed by summing across countries, and may differ slightly from regional aggregates the UN publishes directly, which use a different country grouping.


## Number of people aged 15 to 24 – UN WPP
The total population, measured on 1 July of the year shown. This only includes people aged 15-24.
Last updated: July 12, 2024  
Date range: 1950–2023  
Unit: people  


### How to cite this data

#### In-line citation
If you have limited space (e.g. in data visualizations), you can use this abbreviated in-line citation:  
UN, World Population Prospects (2024) – processed by Our World in Data

#### Full citation
UN, World Population Prospects (2024) – processed by Our World in Data. “Number of people aged 15 to 24 – UN WPP” [dataset]. United Nations, “World Population Prospects”; United Nations, “World Population Prospects - Interim Update” [original data].
Source: UN, World Population Prospects (2024) – processed by Our World In Data

### Sources

#### United Nations – World Population Prospects
Retrieved on: 2024-07-11  
Retrieved from: https://population.un.org/wpp/downloads/  

#### United Nations – World Population Prospects - Interim Update
Retrieved on: 2026-03-31  
Retrieved from: https://population.un.org/wpp/downloads/  

#### Notes on our processing step for this indicator
The UN publishes population by single year of age. We aggregate these into the broader age groups shown here (e.g. 0–14, 15–64, 65+, 18+, 15–49). Our continental aggregates (Africa, Asia, Europe, North America, South America, Oceania) are computed by summing across countries, and may differ slightly from regional aggregates the UN publishes directly, which use a different country grouping.


## Number of people aged 5 to 14 – UN WPP
The total population, measured on 1 July of the year shown. This only includes people aged 5-14.
Last updated: July 12, 2024  
Date range: 1950–2023  
Unit: people  


### How to cite this data

#### In-line citation
If you have limited space (e.g. in data visualizations), you can use this abbreviated in-line citation:  
UN, World Population Prospects (2024) – processed by Our World in Data

#### Full citation
UN, World Population Prospects (2024) – processed by Our World in Data. “Number of people aged 5 to 14 – UN WPP” [dataset]. United Nations, “World Population Prospects”; United Nations, “World Population Prospects - Interim Update” [original data].
Source: UN, World Population Prospects (2024) – processed by Our World In Data

### Sources

#### United Nations – World Population Prospects
Retrieved on: 2024-07-11  
Retrieved from: https://population.un.org/wpp/downloads/  

#### United Nations – World Population Prospects - Interim Update
Retrieved on: 2026-03-31  
Retrieved from: https://population.un.org/wpp/downloads/  

#### Notes on our processing step for this indicator
The UN publishes population by single year of age. We aggregate these into the broader age groups shown here (e.g. 0–14, 15–64, 65+, 18+, 15–49). Our continental aggregates (Africa, Asia, Europe, North America, South America, Oceania) are computed by summing across countries, and may differ slightly from regional aggregates the UN publishes directly, which use a different country grouping.


    