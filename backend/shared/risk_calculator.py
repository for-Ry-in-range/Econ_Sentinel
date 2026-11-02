"""
Calculates risk scores and severity levels based on the percent
change in the 30-day moving average.
"""

from typing import Dict, List, Optional
from enum import Enum


class Severity(str, Enum):
    """3 risk severity levels, plus one for when there isn't enough history to judge"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    INSUFFICIENT_DATA = "insufficient_data"


class RiskCalculator:
    """Calculates risk scores and severity based on percent change"""

    NORMAL_THRESHOLD = 5.0  # < 5% change
    WARNING_THRESHOLD = 15.0  # 5% to 15% change
    # Critical is > 15% change

    # Fewer earlier data points than this in the window and the average means nothing
    MIN_BASELINE_POINTS = 3

    # 0 or below means investors are not confident about the future
    YIELD_CURVE_METRIC = "yield_curve_10y2y"
    YIELD_CURVE_WARNING_LEVEL = 0.0
    YIELD_CURVE_CRITICAL_LEVEL = -0.25

    @staticmethod
    def calculate_percent_change(current_value: float, moving_avg: float):
        """
        Calculate percent change in moving average.
        Args:
            current_value: Current data point value
            moving_avg: 30-day moving averaGe            
        Returns:
            Percent change
        """
        if moving_avg == 0:
            return 0.0
        return ((current_value - moving_avg) / moving_avg) * 100.0
    
    @staticmethod
    def calculate_risk_score(pct_change: float) -> int:
        """
        Calculate risk score out of 100 based on percent change
        Args:
            pct_change: Percent change
        Returns:
            risk score out of 100
        """
        abs_change = abs(pct_change)
        
        if abs_change < RiskCalculator.NORMAL_THRESHOLD:
            # Normal: 0-30 risk score range
            return min(30, int(abs_change * 6))
        elif abs_change < RiskCalculator.WARNING_THRESHOLD:
            # Warning: 31-70 risk score range
            base_score = 31
            range_size = abs_change - RiskCalculator.NORMAL_THRESHOLD
            max_range = RiskCalculator.WARNING_THRESHOLD - RiskCalculator.NORMAL_THRESHOLD
            return base_score + int((range_size / max_range) * 39)
        else:
            # Critical: 71-100 risk score range
            base_score = 71
            range_size = abs_change - RiskCalculator.WARNING_THRESHOLD
            # Cap at 100, assume anything > 50% change is max risk
            additional_score = min(29, int((range_size / 35.0) * 29))
            return base_score + additional_score
    
    @staticmethod
    def determine_severity(pct_change: float) -> Severity:
        """
        Determine severity level based on percent change
        Args:
            pct_change: Percent change
        Returns:
            Severity
        """
        abs_change = abs(pct_change)
        
        if abs_change < RiskCalculator.NORMAL_THRESHOLD:
            return Severity.NORMAL
        elif abs_change < RiskCalculator.WARNING_THRESHOLD:
            return Severity.WARNING
        else:
            return Severity.CRITICAL
    
    @staticmethod
    def calculate_risk(current_value: float, moving_avg: float) -> Dict[str, any]:
        """
        Create complete risk assessment.
        Args:
            current_value: Current data point value
            moving_avg: 30-day moving average
        Returns:
            Dict of pct_change, risk_score, severity
        """
        pct_change = RiskCalculator.calculate_percent_change(current_value, moving_avg)
        risk_score = RiskCalculator.calculate_risk_score(pct_change)
        severity = RiskCalculator.determine_severity(pct_change)
        return {
            "pct_change": round(pct_change, 2),
            "risk_score": risk_score,
            "severity": severity.value
        }

    @staticmethod
    def assess_yield_curve_level(current_value: float) -> Dict[str, any]:
        """
        Severity for the 10Y-2Y spread based on its value, not it's change in value
        """
        if current_value > RiskCalculator.YIELD_CURVE_WARNING_LEVEL:
            return {"risk_score": 0, "severity": Severity.NORMAL.value}

        if current_value > RiskCalculator.YIELD_CURVE_CRITICAL_LEVEL:
            # Warning: 31-70
            # Make risk score based on how deep into the critical zone the current val is
            span = RiskCalculator.YIELD_CURVE_WARNING_LEVEL - RiskCalculator.YIELD_CURVE_CRITICAL_LEVEL
            depth = RiskCalculator.YIELD_CURVE_WARNING_LEVEL - current_value
            return {"risk_score": 31 + int((depth / span) * 39), "severity": Severity.WARNING.value}

        # Critical: 71-100
        depth_past_critical = RiskCalculator.YIELD_CURVE_CRITICAL_LEVEL - current_value
        risk_score = 71 + min(29, int((depth_past_critical / 1.0) * 29))
        return {"risk_score": risk_score, "severity": Severity.CRITICAL.value}

    @staticmethod
    def assess(current_value: float, baseline_values: List[float], metric: Optional[str] = None) -> Dict[str, any]:
        """
        Create complete risk assessment from the earlier values in the moving average window.
        """
        moving_avg = sum(baseline_values) / len(baseline_values) if baseline_values else None
        pct_change = round(RiskCalculator.calculate_percent_change(current_value, moving_avg), 2) \
            if moving_avg is not None else None

        if metric == RiskCalculator.YIELD_CURVE_METRIC:
            return {"moving_avg": moving_avg, "pct_change": pct_change,
                    **RiskCalculator.assess_yield_curve_level(current_value)}

        if len(baseline_values) < RiskCalculator.MIN_BASELINE_POINTS:
            return {
                "moving_avg": moving_avg,
                "pct_change": None,
                "risk_score": None,
                "severity": Severity.INSUFFICIENT_DATA.value
            }

        return {"moving_avg": moving_avg, **RiskCalculator.calculate_risk(current_value, moving_avg)}
