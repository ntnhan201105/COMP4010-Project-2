import json
import os
import pandas as pd

# Load the demographics parquet to extract all unique country ISO codes and names
demographics_path = 'data/demographics.parquet'
if os.path.exists(demographics_path):
    df = pd.read_parquet(demographics_path)
    countries_df = df[['country', 'iso_alpha', 'continent']].drop_duplicates()
else:
    # Fallback in case demographics isn't built yet
    countries_df = pd.DataFrame()

# Detailed custom histories for key countries
custom_histories = {
    "VNM": [
        {
            "start": 1950, "end": 1954, 
            "period": "First Indochina War", 
            "details": "Conflict between French forces and the Viet Minh. Ended with the Geneva Accords, splitting the nation at the 17th parallel.",
            "source": "Wikipedia: First Indochina War"
        },
        {
            "start": 1955, "end": 1975, 
            "period": "Vietnam War", 
            "details": "Major Cold War-era conflict between North Vietnam (supported by communist allies) and South Vietnam (supported by the United States). Reunified in 1975.",
            "source": "Wikipedia: Vietnam War"
        },
        {
            "start": 1976, "end": 1985, 
            "period": "Post-War Reunification & Crisis", 
            "details": "Reunification of the country as the Socialist Republic of Vietnam. Marked by severe economic struggles under central planning and border conflicts.",
            "source": "Wikipedia: History of Vietnam since 1975"
        },
        {
            "start": 1986, "end": 2000, 
            "period": "Đổi Mới Economic Reforms", 
            "details": "Introduction of socialist-oriented market economic reforms. Led to rapid modernization, global integration, and declining fertility rates.",
            "source": "Wikipedia: Doi Moi"
        },
        {
            "start": 2001, "end": 2026, 
            "period": "21st Century Integration & Growth", 
            "details": "Steady GDP growth, poverty reduction, stable demographics, and integration as a global manufacturing hub.",
            "source": "Wikipedia: Modern history of Vietnam"
        }
    ],
    "USA": [
        {
            "start": 1950, "end": 1953, 
            "period": "Korean War & Post-WWII Boom", 
            "details": "Military conflict in Korea and peak of the post-WWII baby boom. Industrial expansion and rise of consumer culture.",
            "source": "Wikipedia: History of the United States (1945-1964)"
        },
        {
            "start": 1954, "end": 1968, 
            "period": "Civil Rights Era & Space Race", 
            "details": "Major social struggles for racial equality. Launch of the Space Race, escalation of the Cold War, and rising involvement in Vietnam.",
            "source": "Wikipedia: Civil Rights Movement"
        },
        {
            "start": 1969, "end": 1980, 
            "period": "Stagflation, Watergate & Detente", 
            "details": "Economic challenges including the oil crisis and stagflation. Political disillusionment due to Watergate, and the end of the Vietnam War.",
            "source": "Wikipedia: History of the United States (1964-1980)"
        },
        {
            "start": 1981, "end": 1991, 
            "period": "Reagan Era & End of Cold War", 
            "details": "Reaganomics, tax cuts, deregulation, intense military competition, and the eventual dissolution of the Soviet Union in 1991.",
            "source": "Wikipedia: History of the United States (1980-1991)"
        },
        {
            "start": 1992, "end": 2000, 
            "period": "Dot-com Boom & Clinton Presidency", 
            "details": "Rapid economic growth fueled by the commercialization of the internet, alongside budget surpluses and globalization.",
            "source": "Wikipedia: History of the United States (1991-2008)"
        },
        {
            "start": 2001, "end": 2008, 
            "period": "War on Terror & Financial Crisis", 
            "details": "The September 11 attacks leading to wars in Afghanistan and Iraq. Ended with the 2008 subprime mortgage crisis and Great Recession.",
            "source": "Wikipedia: History of the United States (2008-present)"
        },
        {
            "start": 2009, "end": 2019, 
            "period": "Post-Recession & Tech Expansion", 
            "details": "Slow economic recovery, polarization, rapid expansion of mobile computing, social media, and shale oil boom.",
            "source": "Wikipedia: History of the United States (2008-present)"
        },
        {
            "start": 2020, "end": 2026, 
            "period": "COVID-19 & Geopolitical Shifts", 
            "details": "COVID-19 pandemic, economic stimulus, high inflation, racial justice movements, and major geopolitical tensions.",
            "source": "Wikipedia: History of the United States (2008-present)"
        }
    ],
    "CHN": [
        {
            "start": 1950, "end": 1957, 
            "period": "Early PRC & First Five-Year Plan", 
            "details": "Establishment of the People's Republic of China, land reform, Korean War involvement, and Soviet-style planned industrialization.",
            "source": "Wikipedia: History of the People's Republic of China (1949-1976)"
        },
        {
            "start": 1958, "end": 1961, 
            "period": "Great Leap Forward", 
            "details": "Industrialization and collectivization campaign. Led to severe economic disruption and the Great Chinese Famine.",
            "source": "Wikipedia: Great Leap Forward"
        },
        {
            "start": 1962, "end": 1965, 
            "period": "Readjustment & Recovery", 
            "details": "Moderate economic reforms under Liu Shaoqi and Deng Xiaoping to restore agricultural and industrial output.",
            "source": "Wikipedia: History of the People's Republic of China (1949-1976)"
        },
        {
            "start": 1966, "end": 1976, 
            "period": "Cultural Revolution", 
            "details": "A decade of political and social upheaval initiated by Mao Zedong. Re-assertion of ideological purity, resulting in severe disruption.",
            "source": "Wikipedia: Cultural Revolution"
        },
        {
            "start": 1977, "end": 1989, 
            "period": "Economic Reform & Opening Up", 
            "details": "Deng Xiaoping launches market-oriented reforms. Introduction of the One-Child Policy (1979) and creation of Special Economic Zones.",
            "source": "Wikipedia: Chinese economic reform"
        },
        {
            "start": 1990, "end": 2000, 
            "period": "Industrial Boom & WTO Preparation", 
            "details": "Rapid urbanization, massive export-led manufacturing growth, and economic restructuring under Jiang Zemin.",
            "source": "Wikipedia: History of the People's Republic of China (1989-2002)"
        },
        {
            "start": 2001, "end": 2012, 
            "period": "Global Integration & Hyper-Growth", 
            "details": "Accession to the WTO (2001) sparking massive growth. 2008 Beijing Olympics and becoming the world's second-largest economy.",
            "source": "Wikipedia: History of the People's Republic of China (2002-2012)"
        },
        {
            "start": 2013, "end": 2026, 
            "period": "New Era & Demographic Transition", 
            "details": "Belt and Road Initiative, anti-corruption campaigns, ending the One-Child Policy (2016), and onset of population decline.",
            "source": "Wikipedia: History of the People's Republic of China (2012-present)"
        }
    ],
    "IND": [
        {
            "start": 1950, "end": 1964, 
            "period": "Nehruvian Socialist Era", 
            "details": "Consolidation of democratic institutions, secularism, and state-led industrial planning under Prime Minister Jawaharlal Nehru.",
            "source": "Wikipedia: History of the Republic of India"
        },
        {
            "start": 1965, "end": 1974, 
            "period": "Green Revolution & Geopolitical Conflicts", 
            "details": "Agricultural reforms dramatically increasing crop yields. Wars with Pakistan (1965, 1971) and creation of Bangladesh.",
            "source": "Wikipedia: Green Revolution in India"
        },
        {
            "start": 1975, "end": 1977, 
            "period": "The Emergency", 
            "details": "Prime Minister Indira Gandhi declares a state of emergency, suspending civil liberties and democratic processes.",
            "source": "Wikipedia: The Emergency (India)"
        },
        {
            "start": 1978, "end": 1990, 
            "period": "Social Tensions & Political Shifts", 
            "details": "Rise of regional politics, insurgencies in Punjab and Kashmir, and assassination of Indira Gandhi (1984).",
            "source": "Wikipedia: History of the Republic of India"
        },
        {
            "start": 1991, "end": 2000, 
            "period": "Economic Liberalization", 
            "details": "Major economic crisis leads to market reforms, deregulation, and rapid growth of the IT and services sectors.",
            "source": "Wikipedia: Economic liberalisation in India"
        },
        {
            "start": 2001, "end": 2013, 
            "period": "Global Tech Hub & Growth", 
            "details": "Rapid GDP growth, expansion of middle class, digital initiatives, and increased global political influence.",
            "source": "Wikipedia: History of the Republic of India"
        },
        {
            "start": 2014, "end": 2026, 
            "period": "Digital Transformation & Modern Era", 
            "details": "Modi administration policies focusing on digitalization, infrastructure, economic nationalism, and becoming the world's most populous nation.",
            "source": "Wikipedia: History of the Republic of India"
        }
    ],
    "GBR": [
        {
            "start": 1950, "end": 1960, 
            "period": "Post-War Austerity & Decolonization", 
            "details": "Creation of the National Health Service (NHS), post-war reconstruction, Suez Crisis (1956), and initial stages of dismantling the British Empire.",
            "source": "Wikipedia: History of the United Kingdom (1945-present)"
        },
        {
            "start": 1961, "end": 1978, 
            "period": "Swinging Sixties & Economic Struggles", 
            "details": "Social liberalization, cultural boom, rising inflation, industrial disputes, and joining the European Communities (1973).",
            "source": "Wikipedia: History of the United Kingdom (1945-present)"
        },
        {
            "start": 1979, "end": 1990, 
            "period": "Thatcherism Era", 
            "details": "Economic policies focusing on privatization, deregulation, reducing trade union power, and the Falklands War (1982).",
            "source": "Wikipedia: Premiership of Margaret Thatcher"
        },
        {
            "start": 1991, "end": 2007, 
            "period": "New Labour & Economic Boom", 
            "details": "Tony Blair's Premiership, devolution in Scotland/Wales, Good Friday Agreement (1998), and participation in the Iraq War.",
            "source": "Wikipedia: Premiership of Tony Blair"
        },
        {
            "start": 2008, "end": 2015, 
            "period": "Austerity & Coalition Government", 
            "details": "Response to the 2008 financial crisis, spending cuts under the Conservative-Liberal Democrat coalition, and 2014 Scottish Independence referendum.",
            "source": "Wikipedia: History of the United Kingdom (1945-present)"
        },
        {
            "start": 2016, "end": 2026, 
            "period": "Brexit & Post-Brexit Transition", 
            "details": "EU Membership referendum leading to Brexit. Pandemic response, economic adjustments, and coronation of King Charles III.",
            "source": "Wikipedia: Brexit"
        }
    ],
    "DEU": [
        {
            "start": 1950, "end": 1961, 
            "period": "Wirtschaftswunder & Berlin Wall", 
            "details": "Rapid economic recovery ('Economic Miracle') in West Germany. Construction of the Berlin Wall in 1961 cementing division.",
            "source": "Wikipedia: Wirtschaftswunder"
        },
        {
            "start": 1962, "end": 1989, 
            "period": "Cold War Division & Ostpolitik", 
            "details": "Ostpolitik policies easing tensions between East and West Germany. Ends with the fall of the Berlin Wall in November 1989.",
            "source": "Wikipedia: German division"
        },
        {
            "start": 1990, "end": 1998, 
            "period": "Reunification & Integration", 
            "details": "German Reunification (October 1990), rebuilding the eastern states, and helping establish the European Union (Maastricht Treaty).",
            "source": "Wikipedia: German reunification"
        },
        {
            "start": 1999, "end": 2005, 
            "period": "Introduction of the Euro", 
            "details": "Adoption of the Euro currency, labor market reforms (Hartz reforms), and shifts in foreign policy under Gerhard Schröder.",
            "source": "Wikipedia: Modern history of Germany"
        },
        {
            "start": 2006, "end": 2021, 
            "period": "Merkel Era & European Leadership", 
            "details": "16-year Chancellorship of Angela Merkel. Leading Europe through the Euro crisis, 2015 refugee crisis, and COVID-19 pandemic.",
            "source": "Wikipedia: Chancellorship of Angela Merkel"
        },
        {
            "start": 2022, "end": 2026, 
            "period": "Zeitenwende & Energy Transition", 
            "details": "Major shift in German foreign and defense policy ('Zeitenwende') following the Ukraine war, and transition away from Russian gas.",
            "source": "Wikipedia: Zeitenwende"
        }
    ],
    "JPN": [
        {
            "start": 1950, "end": 1954, 
            "period": "Post-WWII Occupation & Recovery", 
            "details": "End of Allied occupation (1952), economic recovery spurred by the Korean War demand, and initial industrial reforms.",
            "source": "Wikipedia: Post-occupation Japan"
        },
        {
            "start": 1955, "end": 1973, 
            "period": "Japanese Economic Miracle", 
            "details": "Period of record-breaking economic growth, technological development, hosting the 1964 Tokyo Olympics, and rising exports.",
            "source": "Wikipedia: Japanese economic miracle"
        },
        {
            "start": 1974, "end": 1985, 
            "period": "Oil Shock & High-Tech Transition", 
            "details": "Adjustments to oil crises, shift to high-efficiency manufacturing, semiconductor dominance, and automotive exports.",
            "source": "Wikipedia: Economic history of Japan"
        },
        {
            "start": 1986, "end": 1991, 
            "period": "Asset Price Bubble", 
            "details": "Extreme real estate and stock market speculation. Led to massive asset prices and corporate expansions.",
            "source": "Wikipedia: Japanese asset price bubble"
        },
        {
            "start": 1992, "end": 2012, 
            "period": "The Lost Decades", 
            "details": "Economic stagnation, deflation, banking crises, and demographic shift toward an aging and shrinking population.",
            "source": "Wikipedia: Lost Decades"
        },
        {
            "start": 2013, "end": 2020, 
            "period": "Abenomics Era", 
            "details": "Economic reforms ('three arrows') under Prime Minister Shinzo Abe. Prep for the 2020 Olympics (delayed to 2021).",
            "source": "Wikipedia: Abenomics"
        },
        {
            "start": 2021, "end": 2026, 
            "period": "Reiwa Modern Era", 
            "details": "Post-pandemic tourism recovery, semiconductor supply chain rebuilding, rising inflation, and severe labor shortages.",
            "source": "Wikipedia: Reiwa era"
        }
    ],
    "BRA": [
        {
            "start": 1950, "end": 1963, 
            "period": "Populist Republic & Brasilia", 
            "details": "Industrialization efforts, construction and inauguration of the new capital Brasília (1960) under President Juscelino Kubitschek.",
            "source": "Wikipedia: Fourth Brazilian Republic"
        },
        {
            "start": 1964, "end": 1985, 
            "period": "Military Dictatorship Era", 
            "details": "Military coup establishes a dictatorship. Period of economic miracle in the early 70s, followed by hyperinflation and debt crisis.",
            "source": "Wikipedia: Military dictatorship in Brazil"
        },
        {
            "start": 1986, "end": 1994, 
            "period": "Redemocratization & Hyperinflation", 
            "details": "Return to democracy, a new Constitution (1988), and various economic plans to fight hyperinflation, culminating in the Plano Real (1994).",
            "source": "Wikipedia: History of Brazil (1985-present)"
        },
        {
            "start": 1995, "end": 2002, 
            "period": "Stabilization & Privatization", 
            "details": "Economic stabilization, social welfare reforms, and privatization of state companies under President Fernando Henrique Cardoso.",
            "source": "Wikipedia: History of Brazil (1985-present)"
        },
        {
            "start": 2003, "end": 2013, 
            "period": "Commodity Boom & Social Programs", 
            "details": "High economic growth driven by global commodity demand, expansion of social programs (Bolsa Família) under Lula da Silva.",
            "source": "Wikipedia: History of Brazil (1985-present)"
        },
        {
            "start": 2014, "end": 2026, 
            "period": "Political Crisis & Polarized Era", 
            "details": "Impeachment of Dilma Rousseff, Operation Car Wash corruption probe, presidency of Jair Bolsonaro, COVID-19 impact, and return of Lula.",
            "source": "Wikipedia: History of Brazil (1985-present)"
        }
    ],
    "ZAF": [
        {
            "start": 1950, "end": 1959, 
            "period": "Institutionalization of Apartheid", 
            "details": "National Party codifies racial segregation into law (Group Areas Act, Population Registration Act). Rising resistance.",
            "source": "Wikipedia: Apartheid"
        },
        {
            "start": 1960, "end": 1975, 
            "period": "Sharpeville & Armed Struggle", 
            "details": "Sharpeville massacre (1960), banning of liberation movements (ANC, PAC), and imprisonment of Nelson Mandela.",
            "source": "Wikipedia: History of South Africa (1948-1994)"
        },
        {
            "start": 1976, "end": 1989, 
            "period": "Soweto Uprising & State of Emergency", 
            "details": "Soweto student uprisings (1976), increasing international sanctions and boycotts, and domestic state of emergency declarations.",
            "source": "Wikipedia: Soweto uprising"
        },
        {
            "start": 1990, "end": 1994, 
            "period": "Transition to Democracy", 
            "details": "Unbanning of political parties, release of Nelson Mandela (1990), negotiations to end apartheid, and first democratic elections (1994).",
            "source": "Wikipedia: Negotiations to end apartheid in South Africa"
        },
        {
            "start": 1995, "end": 2008, 
            "period": "Mandela & Mbeki Presidencies", 
            "details": "Reconstruction and Development Programme, adoption of a new Constitution, and reconciliation efforts via the Truth Commission.",
            "source": "Wikipedia: History of South Africa (1994-present)"
        },
        {
            "start": 2009, "end": 2018, 
            "period": "Zuma Presidency & State Capture", 
            "details": "Economic challenges, high unemployment, allegations of state capture and corruption, leading to Zuma's resignation.",
            "source": "Wikipedia: History of South Africa (1994-present)"
        },
        {
            "start": 2019, "end": 2026, 
            "period": "Ramaphosa Administration & Power Crisis", 
            "details": "Efforts to reform state enterprises, severe electricity load shedding (Eskom crisis), and the formation of a coalition government (2024).",
            "source": "Wikipedia: History of South Africa (1994-present)"
        }
    ]
}

# Regional fallbacks to generate timelines for remaining countries
regional_fallbacks = {
    "Africa": [
        {
            "start": 1950, "end": 1969, 
            "period": "Decolonization & Early Independence", 
            "details": "A wave of independence movements sweep the continent, ending colonial rule for many nations and starting self-determination.",
            "source": "Wikipedia: Decolonization of Africa"
        },
        {
            "start": 1970, "end": 1989, 
            "period": "Post-Independence Consolidation", 
            "details": "Nations face economic structural adjustment programs, border conflicts, and shifts toward single-party systems or military rule.",
            "source": "Wikipedia: History of Africa"
        },
        {
            "start": 1990, "end": 2005, 
            "period": "Democratic Transitions & Reforms", 
            "details": "Return of multiparty elections, peace processes in regional conflicts, and early initiatives for pan-African economic cooperation.",
            "source": "Wikipedia: Democratization in Africa"
        },
        {
            "start": 2006, "end": 2026, 
            "period": "Digital Growth & Urbanization", 
            "details": "Rapid urbanization, mobile technology revolution (e.g., mobile banking), rising demographic youth dividend, and investment in infrastructure.",
            "source": "Wikipedia: Modern history of Africa"
        }
    ],
    "Asia": [
        {
            "start": 1950, "end": 1969, 
            "period": "Post-War Reconstruction & Decolonization", 
            "details": "Recovery from WWII, gaining of sovereignty from Western empires, and beginning of national development programs.",
            "source": "Wikipedia: Decolonization of Asia"
        },
        {
            "start": 1970, "end": 1989, 
            "period": "Industrialization & Geopolitics", 
            "details": "Rise of export-oriented manufacturing, agricultural Green Revolution, and navigating Cold War alignment.",
            "source": "Wikipedia: History of Asia"
        },
        {
            "start": 1990, "end": 2005, 
            "period": "Financial Crisis & Globalization", 
            "details": "Rapid growth followed by the 1997 Asian Financial Crisis. Gradual recovery, digitalization, and integration into global supply chains.",
            "source": "Wikipedia: 1997 Asian financial crisis"
        },
        {
            "start": 2006, "end": 2026, 
            "period": "Tech Leadership & Urban Transformation", 
            "details": "Becoming a global hub for tech manufacturing, massive infrastructure projects, rise of megacities, and stable demographics.",
            "source": "Wikipedia: History of Asia"
        }
    ],
    "Europe": [
        {
            "start": 1950, "end": 1969, 
            "period": "Post-War Reconstruction & Cold War", 
            "details": "Marshall Plan aid, rebuilding of industrial infrastructure, and establishment of early European treaties (ECSC, EEC).",
            "source": "Wikipedia: History of Europe"
        },
        {
            "start": 1970, "end": 1989, 
            "period": "Cold War Stagnation & Ostpolitik", 
            "details": "Economic challenges of the 70s, rise of social movements, and eventual collapse of communist regimes in Eastern Europe in 1989.",
            "source": "Wikipedia: Cold War"
        },
        {
            "start": 1990, "end": 2005, 
            "period": "European Integration & Expansion", 
            "details": "Creation of the European Union (1993), launch of the Euro (1999/2002), and expansion of the EU to Eastern European nations.",
            "source": "Wikipedia: European integration"
        },
        {
            "start": 2006, "end": 2026, 
            "period": "Crisis Management & Modern Challenges", 
            "details": "Navigating the Eurozone debt crisis, Brexit, the COVID-19 pandemic, transition to green energy, and security realignment.",
            "source": "Wikipedia: History of the European Union"
        }
    ],
    "Americas": [
        {
            "start": 1950, "end": 1969, 
            "period": "Post-War Industrialization", 
            "details": "Rapid urban growth, political shifts, state-led import-substitution industrialization (ISI) policies, and Cold War political tensions.",
            "source": "Wikipedia: History of Latin America"
        },
        {
            "start": 1970, "end": 1989, 
            "period": "Military Juntas & Debt Crisis", 
            "details": "Establishment of military regimes in several countries, economic volatility, and the 'lost decade' debt crisis of the 1980s.",
            "source": "Wikipedia: Latin American debt crisis"
        },
        {
            "start": 1990, "end": 2005, 
            "period": "Democratization & Neoliberal Reforms", 
            "details": "Widespread transition back to civilian democratic governments, privatization campaigns, and market liberalization policies.",
            "source": "Wikipedia: History of South America"
        },
        {
            "start": 2006, "end": 2026, 
            "period": "Commodity Supercycle & Polarization", 
            "details": "Economic growth driven by the commodity boom, political shifts between left- and right-wing policies, pandemic impacts, and environmental challenges.",
            "source": "Wikipedia: History of South America"
        }
    ]
}

# Compile the final database
events_db = {}

# Process each country in the demographics list
if not countries_df.empty:
    for _, row in countries_df.iterrows():
        iso = row['iso_alpha']
        continent = row['continent']
        
        # If we have a custom history, use it
        if iso in custom_histories:
            events_db[iso] = custom_histories[iso]
        else:
            # Fall back to continent-specific timelines
            if continent == 'Africa':
                events_db[iso] = regional_fallbacks['Africa']
            elif continent == 'Asia':
                events_db[iso] = regional_fallbacks['Asia']
            elif continent == 'Europe':
                events_db[iso] = regional_fallbacks['Europe']
            elif continent == 'Americas':
                events_db[iso] = regional_fallbacks['Americas']
            else:
                # General fallback for Oceania / other cases
                events_db[iso] = regional_fallbacks['Americas']  # Default fallback
else:
    # If demographics file wasn't loaded, create a default database with just custom entries
    events_db = custom_histories

# Write the final JSON file
os.makedirs('data', exist_ok=True)
with open('data/historical_events.json', 'w', encoding='utf-8') as f:
    json.dump(events_db, f, indent=2, ensure_ascii=False)

print(f"Generated historical events database for {len(events_db)} countries.")
print("Saved to data/historical_events.json")
