import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from lambdas.analysis import handler


class FakeDB:
    """In-memory fake representation of DynamoDB database, and its methods"""

    def __init__(self):
        self.rows = {}
        self.saves = 0
        self.rules = []  # alert rules, for every metric

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

    def get_all_metrics(self):
        return sorted({m for m, _ in self.rows})

    def get_latest_score(self, metric):
        rows_for_metric = [row for (m, _), row in sorted(self.rows.items()) if m == metric]
        return rows_for_metric[-1] if rows_for_metric else None

    def get_alert_rules_for_metric(self, metric):
        return [rule for rule in self.rules if rule['metric'] == metric]


# Fixture: runs first (when it's in the parameter of the test) to setup before the test runs

@pytest.fixture
def db():
    fake = FakeDB()
    # Temporarily put the fake DB in place of the real
    with patch.object(handler, 'dynamodb_client', fake):
        yield fake


# Replicate being able to check alerts that are triggered
@pytest.fixture
def alerts():
    with patch.object(handler, 'trigger_alerts') as mock:
        yield mock


def days_ago(n):
    """Return the date n days before today"""
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def ts(n):
    return f"{days_ago(n)}T00:00:00Z"


def s3_event(payload):  # payload: dict representing the S3 contents
    s3 = MagicMock()
    s3.get_object.return_value = {  # What to return when get_object is called
        'ContentType': 'application/json',
        'Body': io.BytesIO(json.dumps(payload).encode('utf-8')),
    }
    event = {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': 'backfill/fred/x.json'}}}]}
    with patch.object(handler, 's3_client', s3):
        return handler.lambda_handler(event, None)


def weekly_payload(values, backfill):
    """Create the dict payload for s3_event, using the values list"""
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
    # One week apart:
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
    alerts.assert_called_once()


def test_backfill_rescores_rows_the_daily_job_already_wrote(db, alerts):
    # Daily job ran before backfill, with no history
    db.rows[('initial_jobless_claims', ts(0))] = {'value': 130.0, 'severity': 'insufficient_data'}

    s3_event(weekly_payload([100, 100, 100, 100, 130], backfill=True))

    assert db.rows[('initial_jobless_claims', ts(0))]['severity'] == 'critical'

    # Alert shouldn't be triggered
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


def test_composite_index_updates_after_a_real_daily_event(db, alerts):
    db.rows[('yield_curve_10y2y', ts(1))] = {'value': -0.40, 'risk_score': 90, 'severity': 'critical'}
    for k in (28, 21, 14, 7):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0, 'risk_score': 0, 'severity': 'normal'}

    s3_event(weekly_payload([100, 100, 100, 100, 100], backfill=False))

    composite_rows = [row for (m, _), row in db.rows.items() if m == 'composite_stress_index']
    assert len(composite_rows) == 1
    assert composite_rows[0]['risk_score'] == 60
    assert composite_rows[0]['severity'] == 'warning'
    alerts.assert_not_called()  # the jobless claims observation itself didn't change


def test_composite_index_not_updated_for_backfill_only_event(db, alerts):
    # Set up mock DynamoDB data
    db.rows[('yield_curve_10y2y', ts(1))] = {'value': -0.40, 'risk_score': 90, 'severity': 'critical'}
    # Add backfill data to S3, which calls the handler
    s3_event(weekly_payload([100, 100, 100, 100, 130, 100], backfill=True))

    # Shouldn't be any composite index in DynamoDB
    assert not any(m == 'composite_stress_index' for (m, _) in db.rows)


def test_composite_index_saves_what_each_metric_contributed(db, alerts):
    db.rows[('yield_curve_10y2y', ts(1))] = {'value': -0.40, 'risk_score': 90, 'severity': 'critical'}
    for k in (28, 21, 14, 7):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0, 'risk_score': 0, 'severity': 'normal'}

    s3_event(weekly_payload([100], backfill=False)) # Today's data

    composite = db.get_latest_score('composite_stress_index')
    assert composite['components'] == [
        {'metric': 'initial_jobless_claims', 'risk_score': 0, 'weight': 1.0},
        {'metric': 'yield_curve_10y2y', 'risk_score': 90, 'weight': 2.0},
    ]


# Lets the composite alert code go all the way to "sending", then records the emails
@pytest.fixture
def composite_emails():
    with patch.object(handler, 'SENDER_EMAIL', 'alerts@example.com'), \
            patch.object(handler, '_send_email') as mock: # if _send_email is called, it is recorded but nothing happens
        yield mock # gives the function using this fixture to check any of the patched objects


# Make a fake composite rule dict that can be inputted into the rules DB
def composite_rule(threshold, enabled=True, email='user@example.com'):
    return {'user_id': 'u1', 'metric': 'composite_stress_index', 'threshold': threshold,
            'enabled': enabled, 'email': email}


def composite(risk_score):
    return {'risk_score': risk_score, 'severity': 'warning', 'contributors': ['m'],
            'components': [{'metric': 'm', 'risk_score': risk_score, 'weight': 1.0}]}


def test_composite_alert_sent_when_a_daily_event_pushes_it_over_the_threshold(db, alerts, composite_emails):
    db.rules.append(composite_rule(50))
    db.rows[('yield_curve_10y2y', ts(1))] = {'value': -0.40, 'risk_score': 90, 'severity': 'critical'}
    for k in (28, 21, 14, 7):
        db.rows[('initial_jobless_claims', ts(k))] = {'value': 100.0, 'risk_score': 0, 'severity': 'normal'}

    s3_event(weekly_payload([100, 100, 100, 100, 100], backfill=False))  # composite becomes 60

    composite_emails.assert_called_once()
    recipient, subject, body, _ = composite_emails.call_args.args
    assert recipient == 'user@example.com'
    assert 'Composite Stress Index' in subject
    assert '60/100' in body
    assert 'yield_curve_10y2y: 90/100 (weight 2)' in body


@pytest.mark.parametrize('previous_score, new_score, expected_emails', [
    (None, 60, 1),  # first composite ever, is already over threshold
    (40, 60, 1),    # crossed the threshold
    (50, 60, 0),    # was already at the threshold, so the user has been told
    (70, 60, 0),    # still over, but falling
    (40, 49, 0),    # still under
    (40, 50, 1),    # reaching the threshold exactly counts
])
def test_composite_alert_only_when_threshold_is_crossed(db, composite_emails, previous_score, new_score, expected_emails):
    db.rules.append(composite_rule(50))
    handler.trigger_composite_alerts(composite(new_score), previous_score)
    assert composite_emails.call_count == expected_emails


def test_composite_alert_skips_disabled_rules_and_rules_without_an_email(db, composite_emails):
    db.rules.append(composite_rule(50, enabled=False))
    db.rules.append(composite_rule(50, email=None))
    handler.trigger_composite_alerts(composite(60), 40)
    composite_emails.assert_not_called()


def test_composite_alert_uses_each_users_own_threshold(db, composite_emails):
    db.rules.append(composite_rule(31, email='low@example.com'))
    db.rules.append(composite_rule(71, email='high@example.com'))
    handler.trigger_composite_alerts(composite(60), 20)
    assert [call.args[0] for call in composite_emails.call_args_list] == ['low@example.com']
