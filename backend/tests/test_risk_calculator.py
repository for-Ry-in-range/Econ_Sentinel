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


def test_yield_curve_is_scored_by_level_not_pct_change():
    result = RiskCalculator.assess(0.12, [0.05], metric='yield_curve_10y2y')
    assert result['severity'] == 'normal'
    assert result['risk_score'] == 0


def test_yield_curve_inversion_is_warning_not_insufficient_data():
    result = RiskCalculator.assess(-0.10, [], metric='yield_curve_10y2y')
    assert result['severity'] == 'warning'
    assert result['moving_avg'] is None
    assert result['pct_change'] is None


def test_yield_curve_deep_inversion_is_critical():
    result = RiskCalculator.assess(-0.40, [0.05, 0.03], metric='yield_curve_10y2y')
    assert result['severity'] == 'critical'
    assert 71 <= result['risk_score'] <= 100


def test_yield_curve_severity_worsens_as_spread_drops():
    mild = RiskCalculator.assess(-0.05, [], metric='yield_curve_10y2y')
    deep = RiskCalculator.assess(-0.20, [], metric='yield_curve_10y2y')
    assert mild['severity'] == 'warning'
    assert deep['severity'] == 'warning'
    assert deep['risk_score'] > mild['risk_score']


def test_yield_curve_at_exact_levels():
    assert RiskCalculator.assess(0.0, [], metric='yield_curve_10y2y')['severity'] == 'warning'
    assert RiskCalculator.assess(-0.25, [], metric='yield_curve_10y2y')['severity'] == 'critical'
