"""
Calculates risk scores and severity levels based on the percent
change in the 30-day moving average.
"""

from typing import Dict, Optional
from enum import Enum


class Severity(str, Enum):
    """3 risk severity levels"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskCalculator:
    """Calculates risk scores and severity based on percent change"""
    
    NORMAL_THRESHOLD = 5.0  # < 5% change
    WARNING_THRESHOLD = 15.0  # 5% to 15% change
    # Critical is > 15% change
    
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
