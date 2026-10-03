import { useEffect, useState, useCallback } from 'react';
import { metricLabel } from '../config.js';
import Loading from './Loading.jsx';
import ErrorBanner from './ErrorBanner.jsx';

/**
 * Manage the signed-in user's email alert rules
 * Thresholds are percent-change values
 */
export default function AlertsManager({ api, metrics, userEmail, onError }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const [metric, setMetric] = useState('');
  const [threshold, setThreshold] = useState('15');

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

  // Default the metric dropdown to the first available metric.
  useEffect(() => {
    if (!metric && metrics.length > 0) setMetric(metrics[0]);
  }, [metrics, metric]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    const thresholdNum = Number(threshold);
    if (!metric) return setError('Choose a metric.');
    if (Number.isNaN(thresholdNum)) return setError('Threshold must be a number.');

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
      </p>

      {/* If an error occurs, it displays in this ErrorBanner */}
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <form className="alert-form" onSubmit={handleCreate}>
        <label>
          Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {metrics.length === 0 && <option value="">No metrics available</option>}
            {metrics.map((m) => (
              <option key={m} value={m}>
                {metricLabel(m)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Threshold (%)
          <input
            type="number"
            step="0.1"
            min="0"
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
                <td>{Number(rule.threshold)}%</td>
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
