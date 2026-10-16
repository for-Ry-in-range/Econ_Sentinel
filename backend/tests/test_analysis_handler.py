import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from lambdas.analysis import handler


class FakeDB:
    """In-memory stand-in for DynamoDBClient's risk score methods"""

    def __init__(self):
        self.rows = {}
        self.saves = 0

    def get_score(self, metric, timestamp):
        return self.rows.get((metric, timestamp))

    def get_values_before(self, metric, as_of, days=30):
        as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        start = as_of_dt - timedelta(days=days)
        return [
            row['value']
            for (m, ts), row in sorted(self.rows.items())
            if m == metric and start <= datetime.fromisoformat(ts.replace('Z', '+00:00')) < as_of_dt
        ]

    def save_risk_score(self, **item):
        self.saves += 1
        self.rows[(item['metric'], item['timestamp'])] = item


@pytest.fixture
def db():
    fake = FakeDB()
    with patch.object(handler, 'dynamodb_client', fake):
        yield fake


@pytest.fixture
def alerts():
    with patch.object(handler, 'trigger_alerts') as mock:
        yield mock


def days_ago(n):
    # UTC, to match the handler's age check
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def ts(n):
    return f"{days_ago(n)}T00:00:00Z"


def s3_event(payload):
    """Run the handler on one S3 file containing payload"""
    s3 = MagicMock()
    s3.get_object.return_value = {
        'ContentType': 'application/json',
        'Body': io.BytesIO(json.dumps(payload).encode('utf-8')),
    }
    event = {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'backfill/fred/x.json'}}}]}
    with patch.object(handler, 's3_client', s3):
        return handler.lambda_handler(event, None)


def weekly_payload(values, backfill):
    """Weekly observations, the last one dated today"""
    count = len(values)
    payload = {
        'series_id': 'ICSA',
        'metric_name': 'initial_jobless_claims',
        'data': [{'date': days_ago(7 * (count - 1 - i)), 'value': str(v)} for i, v in enumerate(values)],
    }
    if backfill:
        payload['backfill'] = True
    return payload


def test_backfill_scores_in_order_and_never_alerts(db, alerts):
    # The 5th point is +30% on a 4-point average of 100: critical, and only 7 days old
    result = s3_event(weekly_payload([100, 100, 100, 100, 130, 100], backfill=True))

    assert result['processed_count'] == 6
    assert result['errors'] == []
    rows = [db.rows[('initial_jobless_claims', ts(7 * k))] for k in range(5, -1, -1)]
    assert [r['severity'] for r in rows[:3]] == ['insufficient_data'] * 3
    assert rows[3]['severity'] == 'normal'
    assert rows[4]['severity'] == 'critical'
    assert rows[4]['pct_change'] == 30.0
    alerts.assert_not_called()


def test_backfill_flag_must_be_true_not_just_present(db, alerts):
    payload = weekly_payload([100, 100, 100, 100, 130], backfill=False)
    payload['backfill'] = 'no'
    s3_event(payload)
    # The critical point is 0 days old, so with no real backfill flag it alerts
    alerts.assert_called_once()


def test_backfill_rescores_rows_the_daily_job_already_wrote(db, alerts):
    # Daily job ran before backfill, with no history
    db.rows[('initial_jobless_claims', ts(0))] = {'value': 130.0, 'severity': 'insufficient_data'}

    s3_event(weekly_payload([100, 100, 100, 100, 130], backfill=True))

    assert db.rows[('initial_jobless_claims', ts(0))]['severity'] == 'critical'
    alerts.assert_not_called()


def test_rerunning_backfill_gives_the_same_rows(db, alerts):
    payload = weekly_payload([100, 105, 98, 101, 120, 99], backfill=True)
    s3_event(payload)
    first = dict(db.rows)
    s3_event(payload)
    assert db.rows == first


def test_daily_refetch_of_same_weekly_value_is_skipped(db, alerts):
    db.rows[('initial_jobless_claims', ts(3))] = {'value': 130.0, 'severity': 'critical'}

    scored = handler.process_metric('initial_jobless_claims', 130.0, days_ago(3), 'fred/x.json')

    assert scored is False
    assert db.saves == 0
    alerts.assert_not_called()


def test_daily_new_critical_observation_alerts(db, alerts):
    for k in (28, 21, 14, 7):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0}

    assert handler.process_metric('initial_jobless_claims', 130.0, days_ago(0), 'fred/x.json') is True
    alerts.assert_called_once()


def test_daily_revised_value_is_rescored_without_alerting(db, alerts):
    for k in (28, 21, 14, 7):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0}
    db.rows[('initial_jobless_claims', ts(0))] = {'value': 128.0, 'severity': 'critical'}

    assert handler.process_metric('initial_jobless_claims', 130.0, days_ago(0), 'fred/x.json') is True
    assert db.rows[('initial_jobless_claims', ts(0))]['value'] == 130.0
    alerts.assert_not_called()


def test_old_observation_without_backfill_flag_does_not_alert(db, alerts):
    # Safety net: a historical file dropped in without the flag
    for k in (60, 53, 46, 39):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0}

    assert handler.process_metric('initial_jobless_claims', 130.0, days_ago(32), 'fred/x.json') is True
    assert db.rows[('initial_jobless_claims', ts(32))]['severity'] == 'critical'
    alerts.assert_not_called()


def test_insufficient_data_never_alerts(db, alerts):
    handler.process_metric('initial_jobless_claims', 500.0, days_ago(0), 'fred/x.json')
    assert db.rows[('initial_jobless_claims', ts(0))]['severity'] == 'insufficient_data'
    alerts.assert_not_called()


@pytest.mark.parametrize('timestamp, expected', [
    (ts(0), True),
    (ts(handler.ALERT_MAX_AGE_DAYS), True),
    (ts(handler.ALERT_MAX_AGE_DAYS + 1), False),
    ('not a date', False),
])
def test_is_recent_observation(timestamp, expected):
    assert handler.is_recent_observation(timestamp) is expected
