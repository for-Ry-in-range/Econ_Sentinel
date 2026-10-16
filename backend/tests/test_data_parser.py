from shared.data_parser import DataParser


def test_parse_fred_data_returns_every_observation_oldest_first():
    payload = {
        'series_id': 'ICSA',
        'metric_name': 'initial_jobless_claims',
        'data': [
            {'date': '2026-01-17', 'value': '230000'},
            {'date': '2026-01-03', 'value': '210000'},
            {'date': '2026-01-10', 'value': '220000'},
        ],
    }
    results = DataParser.parse_fred_data(payload)
    assert [r['timestamp'] for r in results] == ['2026-01-03', '2026-01-10', '2026-01-17']
    assert [r['value'] for r in results] == [210000.0, 220000.0, 230000.0]
    assert all(r['metric'] == 'initial_jobless_claims' for r in results)


def test_parse_fred_data_skips_bad_points_but_keeps_the_rest():
    payload = {
        'series_id': 'T10Y2Y',
        'data': [
            {'date': '2026-01-02', 'value': '0.55'},
            {'date': '2026-01-05', 'value': 'not a number'},
            {'date': '2026-01-06'},
            {'date': '2026-01-07', 'value': '0.60'},
        ],
    }
    results = DataParser.parse_fred_data(payload)
    assert [r['timestamp'] for r in results] == ['2026-01-02', '2026-01-07']
    # Falls back to series_id when there's no metric_name
    assert results[0]['metric'] == 'T10Y2Y'


def test_parse_fred_data_single_daily_observation():
    payload = {'series_id': 'ICSA', 'metric_name': 'initial_jobless_claims',
               'data': [{'date': '2026-01-10', 'value': '220000'}]}
    assert len(DataParser.parse_fred_data(payload)) == 1


def test_parse_fred_data_simplified_format():
    payload = {'metric': 'initial_jobless_claims', 'value': 220000, 'date': '2026-01-10', 'source': 'fred'}
    results = DataParser.parse_fred_data(payload)
    assert results == [{'metric': 'initial_jobless_claims', 'value': 220000.0,
                        'timestamp': '2026-01-10', 'source': 'fred'}]
