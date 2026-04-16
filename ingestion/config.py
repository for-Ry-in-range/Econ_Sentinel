"""
Config for ingestion
"""

FRED_SERIES = {
    "inflation_rate_cpi": "CPIAUCSL",  # CPI: Urban Consumers
    "ppi_all_commodities": "PPIACO",  # PPI: All Commodities
    "unemployment_rate": "UNRATE",  # Unemployment Rate
}

FREIGHT_FRED_SERIES = {
    "freight_cost_index": "WPU3012",  # PPI: Freight Transportation
    "freight_cost_trucking": "PCU4841484148",  # PPI: Trucking
}

MAJOR_PORTS = ["los_angeles", "long_beach", "new_york", "savannah"]
