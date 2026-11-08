"""
Combines each metric into one combined stress index.
Is stored in DynamoDB.
"""

from typing import Dict, Optional

from .risk_calculator import RiskCalculator, Severity

COMPOSITE_METRIC = "composite_stress_index"

# The yield curve is a little more important than the other metrics
METRIC_WEIGHTS = {
    "yield_curve_10y2y": 2.0,
    "initial_jobless_claims": 1.0,
}
DEFAULT_WEIGHT = 1.0  # any metric not listed above


def compute_composite(latest_scores: Dict[str, Dict]) -> Optional[Dict]:
    weighted_total = 0.0
    weight_total = 0.0
    contributors = []

    for metric, score in latest_scores.items():
        # Metrics with no history yet are excluded
        if not score or score.get('risk_score') is None:
            continue
        weight = METRIC_WEIGHTS.get(metric, DEFAULT_WEIGHT)
        weighted_total += weight * float(score['risk_score'])
        weight_total += weight
        contributors.append(metric)

    if weight_total == 0:
        return None

    risk_score = round(weighted_total / weight_total)
    return {
        "risk_score": risk_score,
        "severity": RiskCalculator.severity_for_score(risk_score).value,
        "contributors": sorted(contributors),
    }
