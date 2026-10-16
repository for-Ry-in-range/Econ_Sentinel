from shared.risk_calculator import RiskCalculator


def test_assess_with_no_history_is_insufficient_data():
    result = RiskCalculator.assess(100.0, [])
    assert result == {
        'moving_avg': None,
        'pct_change': None,
        'risk_score': None,
        'severity': 'insufficient_data',
    }


def test_assess_below_min_points_is_insufficient_data_but_keeps_average():
    result = RiskCalculator.assess(150.0, [100.0, 110.0])
    assert result['severity'] == 'insufficient_data'
    assert result['risk_score'] is None
    assert result['pct_change'] is None
    assert result['moving_avg'] == 105.0


def test_assess_with_enough_history_scores_against_average():
    result = RiskCalculator.assess(120.0, [100.0, 100.0, 100.0])
    assert result['moving_avg'] == 100.0
    assert result['pct_change'] == 20.0
    assert result['severity'] == 'critical'
    assert 71 <= result['risk_score'] <= 100


def test_assess_normal_reading():
    result = RiskCalculator.assess(101.0, [100.0, 100.0, 100.0, 100.0])
    assert result['severity'] == 'normal'
    assert result['pct_change'] == 1.0
