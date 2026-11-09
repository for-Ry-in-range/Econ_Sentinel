from shared.composite_index import compute_composite


def score(risk_score, severity='normal'):
    return {'risk_score': risk_score, 'severity': severity}


def test_no_usable_scores_returns_none():
    assert compute_composite({}) is None
    assert compute_composite({'initial_jobless_claims': None}) is None
    assert compute_composite({'initial_jobless_claims': {'severity': 'insufficient_data', 'risk_score': None}}) is None


def test_single_metric_passes_through():
    result = compute_composite({'initial_jobless_claims': score(80)})
    assert result['risk_score'] == 80
    assert result['severity'] == 'critical' # severity gets calculated in compute_composite
    assert result['contributors'] == ['initial_jobless_claims']


def test_insufficient_data_metric_is_excluded_not_zeroed():
    result = compute_composite({
        'initial_jobless_claims': score(80),
        'yield_curve_10y2y': {'severity': 'insufficient_data', 'risk_score': None},
    })
    assert result['risk_score'] == 80
    assert result['contributors'] == ['initial_jobless_claims']


def test_yield_curve_counts_double():
    # Equal scores, so weighting shouldn't change the result
    equal = compute_composite({
        'initial_jobless_claims': score(40),
        'yield_curve_10y2y': score(40),
    })
    assert equal['risk_score'] == 40

    # But different scores should change based on weighting
    weighted = compute_composite({
        'initial_jobless_claims': score(0),
        'yield_curve_10y2y': score(90),
    })
    assert weighted['risk_score'] == 60


def test_unknown_metric_uses_default_weight():
    result = compute_composite({
        'port_congestion_los_angeles': score(70),
        'initial_jobless_claims': score(50),
    })
    assert result['risk_score'] == 60


def test_severity_bands_match_risk_calculator():
    assert compute_composite({'m': score(30)})['severity'] == 'normal'
    assert compute_composite({'m': score(31)})['severity'] == 'warning'
    assert compute_composite({'m': score(70)})['severity'] == 'warning'
    assert compute_composite({'m': score(71)})['severity'] == 'critical'
