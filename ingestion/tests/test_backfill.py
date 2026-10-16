"""
Run from the repo root:  python -m pytest ingestion/tests
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from ingestion import backfill
from ingestion.fred_client import FREDClient


def fred_response(observations):
    response = MagicMock()
    response.json.return_value = {'observations': observations}
    return response


def test_fetch_series_range_requests_the_whole_range_oldest_first():
    client = FREDClient(api_key='key')
    client.session = MagicMock()
    client.session.get.return_value = fred_response([
        {'date': '2025-09-01', 'value': '0.50'},
        {'date': '2025-09-02', 'value': '.'},
        {'date': '2025-09-03', 'value': '0.52'},
    ])

    result = client.fetch_series_range('T10Y2Y', date(2025, 9, 1), date(2025, 9, 30))

    params = client.session.get.call_args.kwargs['params']
    assert params['sort_order'] == 'asc'
    assert params['observation_start'] == '2025-09-01'
    assert params['observation_end'] == '2025-09-30'
    assert 'limit' not in params
    # FRED's "." missing values are dropped
    assert result == {
        'series_id': 'T10Y2Y',
        'data': [{'date': '2025-09-01', 'value': '0.50'}, {'date': '2025-09-03', 'value': '0.52'}],
    }


def test_fetch_series_range_returns_none_when_empty():
    client = FREDClient(api_key='key')
    client.session = MagicMock()
    client.session.get.return_value = fred_response([{'date': '2025-09-02', 'value': '.'}])
    assert client.fetch_series_range('T10Y2Y', date(2025, 9, 1), date(2025, 9, 30)) is None


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('RAW_DATA_BUCKET_NAME', 'bucket')
    monkeypatch.setenv('FRED_API_KEY', 'key')


def test_backfill_uploads_one_flagged_file_per_series(env):
    series = [
        {'series_id': 'ICSA', 'metric_name': 'initial_jobless_claims', 'data': [{'date': '2025-09-06', 'value': '1'}]},
        {'series_id': 'T10Y2Y', 'metric_name': 'yield_curve_10y2y', 'data': [{'date': '2025-09-02', 'value': '2'}]},
    ]
    with patch.object(backfill, 'FREDClient') as fred_cls, patch.object(backfill, 'S3Storage') as storage_cls:
        fred_cls.return_value.fetch_all_range.return_value = series
        storage_cls.return_value.upload_many.side_effect = lambda payloads: ['k'] * len(payloads)

        backfill.run(['--days', '400'])

        start, end = fred_cls.return_value.fetch_all_range.call_args.args
        assert (end - start).days == 400
        uploads = storage_cls.return_value.upload_many.call_args.args[0]

    assert [(source, metric) for _, source, metric in uploads] == [
        ('backfill/fred', 'initial_jobless_claims'),
        ('backfill/fred', 'yield_curve_10y2y'),
    ]
    assert all(payload['backfill'] is True for payload, _, _ in uploads)


def test_backfill_exits_nonzero_when_an_upload_fails(env):
    with patch.object(backfill, 'FREDClient') as fred_cls, patch.object(backfill, 'S3Storage') as storage_cls:
        fred_cls.return_value.fetch_all_range.return_value = [{'series_id': 'ICSA', 'data': []}]
        storage_cls.return_value.upload_many.return_value = []
        with pytest.raises(SystemExit) as exc:
            backfill.run([])
    assert exc.value.code == 1


def test_backfill_rejects_nonpositive_days(env):
    with pytest.raises(SystemExit):
        backfill.run(['--days', '0'])
