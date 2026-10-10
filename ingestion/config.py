"""
Config for ingestion
"""

FRED_SERIES = {
    "initial_jobless_claims": "ICSA",  # Initial Jobless Claims (weekly)
    "yield_curve_10y2y": "T10Y2Y",  # 10-Year minus 2-Year Treasury Yield Spread (daily)
}

MAJOR_PORTS = ["los_angeles", "long_beach", "new_york", "savannah"]
