import { useEffect, useState, useCallback } from 'react';
import { metricLabel, isScoreBased } from '../config.js';
import Loading from './Loading.jsx';
import ErrorBanner from './ErrorBanner.jsx';

/**
 * JS component that manages the signed-in user's email alert rules
 * Thresholds are percent-change values, except for the composite index,
 * where the threshold is a 0-100 score.
 */

// Score bands from the backend: 31+ is warning, 71+ is critical
const DEFAULT_PCT_THRESHOLD = '15';   // "score changed by a decent amount"
const DEFAULT_SCORE_THRESHOLD = '31'; // "composite index is decently high"
export default function AlertsManager({ api, metrics, userEmail, onError }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const [metric, setMetric] = useState('');
  const [threshold, setThreshold] = useState(DEFAULT_PCT_THRESHOLD);
  const scoreBased = isScoreBased(metric);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const rows = await api.getAlerts();
      setAlerts(rows);
    } catch (err) {
      if (err.name === 'UnauthorizedError') return onError(err);
      setError(err.message || 'Could not load alerts.');
    } finally {
      setLoading(false);
    }
  }, [api, onError]);

  useEffect(() => {
    load();
  }, [load]);

  // Picking a metric resets the threshold to that kind of metric's default,
  // since 15 means something different as a percent than as a score.
  const chooseMetric = useCallback((m) => {
    setMetric(m);
    setThreshold(isScoreBased(m) ? DEFAULT_SCORE_THRESHOLD : DEFAULT_PCT_THRESHOLD);
  }, []);

  // Default the metric dropdown to the first available metric.
  useEffect(() => {
    if (!metric && metrics.length > 0) chooseMetric(metrics[0]);
  }, [metrics, metric, chooseMetric]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    const thresholdNum = Number(threshold);
    if (!metric) return setError('Choose a metric.');
    if (threshold === '' || Number.isNaN(thresholdNum)) return setError('Threshold must be a number.');
    if (scoreBased && (thresholdNum < 0 || thresholdNum > 100)) {
      return setError('The composite index threshold is a score from 0 to 100.');
    }

    setSaving(true);
    try {
      await api.putAlert({
        metric,
        threshold: thresholdNum,
        enabled: true,
        email: userEmail,
      });
      await load();
    } catch (err) {
      if (err.name === 'UnauthorizedError') return onError(err);
      setError(err.message || 'Could not save alert.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (rule) => {
    setError('');
    try {
      await api.putAlert({
        metric: rule.metric,
        threshold: Number(rule.threshold),
        enabled: !rule.enabled,
        email: rule.email || userEmail,
      });
      await load();
    } catch (err) {
      if (err.name === 'UnauthorizedError') return onError(err);
      setError(err.message || 'Could not update alert.');
    }
  };

  const handleDelete = async (ruleMetric) => {
    setError('');
    try {
      await api.deleteAlert(ruleMetric);
      await load();
    } catch (err) {
      if (err.name === 'UnauthorizedError') return onError(err);
      setError(err.message || 'Could not delete alert.');
    }
  };

  return (
    <section className="alerts">
      <h2>Email Alerts</h2>
      <p className="section-sub">
        Get an email when a metric moves more than your threshold (% vs its 30-day average).
        For the composite index, the threshold is a score: you get one email when the index
        rises to it (31 is where "warning" starts, 71 is "critical").
      </p>

      {/* If an error occurs, it displays in this ErrorBanner */}
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <form className="alert-form" onSubmit={handleCreate}>
        <label>
          Metric
          <select value={metric} onChange={(e) => chooseMetric(e.target.value)}>
            {metrics.length === 0 && <option value="">No metrics available</option>}
            {metrics.map((m) => (
              <option key={m} value={m}>
                {metricLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {scoreBased ? 'Threshold (score 0–100)' : 'Threshold (%)'}
          <input
            type="number"
            step={scoreBased ? '1' : '0.1'}
            min="0"
            max={scoreBased ? '100' : undefined}
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
        </label>
        <button className="primary" type="submit" disabled={saving || metrics.length === 0}>
          {saving ? 'Saving…' : 'Add / update alert'}
        </button>
      </form>

      {loading ? (
        <Loading label="Loading alerts…" />
      ) : alerts.length === 0 ? (
        <p className="muted">No alert rules yet.</p>
      ) : (
        <table className="alerts-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Threshold</th>
              <th>Status</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {alerts.map((rule) => (
              <tr key={rule.metric}>
                <td>{metricLabel(rule.metric)}</td>
                <td>
                  {isScoreBased(rule.metric)
                    ? `Score ≥ ${Number(rule.threshold)}`
                    : `${Number(rule.threshold)}%`}
                </td>
                <td>
                  <span className={`pill ${rule.enabled ? 'on' : 'off'}`}>
                    {rule.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </td>
                <td className="row-actions">
                  <button type="button" className="link" onClick={() => handleToggle(rule)}>
                    {rule.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    type="button"
                    className="link danger"
                    onClick={() => handleDelete(rule.metric)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
