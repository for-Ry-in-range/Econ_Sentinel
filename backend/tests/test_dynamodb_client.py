from decimal import Decimal
from unittest.mock import MagicMock, patch

from shared.dynamodb_client import DynamoDBClient


def make_client():
    with patch('shared.dynamodb_client.boto3'):
        client = DynamoDBClient()
    client.risk_scores_table = MagicMock()
    return client


def test_get_values_before_uses_window_before_the_observation_not_today():
    client = make_client()
    as_of = '2025-09-15T00:00:00Z'
    client.risk_scores_table.query.return_value = {'Items': [
        {'metric': 'm', 'timestamp': '2025-08-20T00:00:00Z', 'value': Decimal('1')},
        {'metric': 'm', 'timestamp': '2025-09-01T00:00:00Z', 'value': Decimal('2')},
        {'metric': 'm', 'timestamp': as_of, 'value': Decimal('99')},
    ]}

    values = client.get_values_before('m', as_of, days=30)

    # The observation itself is left out of its own baseline
    assert values == [1.0, 2.0]

    condition = client.risk_scores_table.query.call_args.kwargs['KeyConditionExpression']
    between = condition.get_expression()['values'][1]
    _, start, end = between.get_expression()['values']
    assert start == '2025-08-16T00:00:00Z'
    assert end == as_of


def test_get_values_before_follows_pagination():
    client = make_client()
    client.risk_scores_table.query.side_effect = [
        {'Items': [{'timestamp': '2025-09-01T00:00:00Z', 'value': Decimal('1')}],
         'LastEvaluatedKey': {'k': 1}},
        {'Items': [{'timestamp': '2025-09-02T00:00:00Z', 'value': Decimal('2')}]},
    ]
    assert client.get_values_before('m', '2025-09-15T00:00:00Z') == [1.0, 2.0]
    assert client.risk_scores_table.query.call_args.kwargs['ExclusiveStartKey'] == {'k': 1}


def test_save_risk_score_leaves_out_scores_that_could_not_be_calculated():
    client = make_client()
    client.save_risk_score(
        metric='m', timestamp='2025-09-15T00:00:00Z', value=5.0,
        moving_avg_30d=None, pct_change=None, risk_score=None,
        severity='insufficient_data', source_object_key='key.json',
    )
    item = client.risk_scores_table.put_item.call_args.kwargs['Item']
    assert 'moving_avg_30d' not in item
    assert 'pct_change' not in item
    assert 'risk_score' not in item
    assert item['severity'] == 'insufficient_data'
    assert item['value'] == Decimal('5.0')


def test_get_score_returns_none_when_missing():
    client = make_client()
    client.risk_scores_table.get_item.return_value = {}
    assert client.get_score('m', '2025-09-15T00:00:00Z') is None
