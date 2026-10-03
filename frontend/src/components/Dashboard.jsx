import { useEffect, useMemo, useState, useCallback } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { createApiClient } from '../api/client.js';
import ScoreCard from './ScoreCard.jsx';
import RiskChart from './RiskChart.jsx';
import AlertsManager from './AlertsManager.jsx';
import Loading from './Loading.jsx';
import ErrorBanner from './ErrorBanner.jsx';

export default function Dashboard() {
  const { user, signOut, getIdToken } = useAuth();

  // API client that removes the need to create a new API client every render
  const api = useMemo(() => createApiClient(getIdToken), [getIdToken]);

  const [metrics, setMetrics] = useState([]);
  const [scores, setScores] = useState({}); // metric -> latest score | null
  const [selected, setSelected] = useState(null);
  const [series, setSeries] = useState([]);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // If a request reports the session is gone, sign out (back to login).
  const handleAuthError = useCallback(
    (err) => {
      if (err?.name === 'UnauthorizedError') {
        signOut();
        return true;
      }
      return false;
    },
    [signOut]
  );

  // Load metrics + each metric's latest score.
  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const metricList = await api.getMetrics();
        if (!active) return;
        setMetrics(metricList);
        if (metricList.length > 0) setSelected((cur) => cur || metricList[0]);

        const entries = await Promise.all(
          metricList.map(async (m) => [m, await api.getLatestScore(m)])
        );
        if (!active) return;
        setScores(Object.fromEntries(entries));
      } catch (err) {
        if (!active) return;
        if (!handleAuthError(err)) setError(err.message || 'Failed to load dashboard.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [api, handleAuthError]);

  // Load the time series for the selected metric.
  useEffect(() => {
    if (!selected) return;
    let active = true;
    (async () => {
      setSeriesLoading(true);
      try {
        const data = await api.getTimeSeries(selected);
        if (active) setSeries(data);
      } catch (err) {
        if (active && !handleAuthError(err)) {
          setError(err.message || 'Failed to load metric history.');
        }
      } finally {
        if (active) setSeriesLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [api, selected, handleAuthError]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand">Econ Sentinel</span>
          <span className="topbar-sub">Macroeconomic stress monitor</span>
        </div>
        <div className="topbar-user">
          <span className="user-email">{user?.email}</span>
          <button type="button" className="secondary" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <main className="content">
        <ErrorBanner message={error} onDismiss={() => setError('')} />

        {loading ? (
          <Loading label="Loading economic scores…" />
        ) : metrics.length === 0 ? (
          <div className="empty-state">
            <h2>No data yet</h2>
            <p>
              No risk scores have been calculated. Once the daily ingestion runs and the
              analysis Lambda processes data, metrics will appear here.
            </p>
          </div>
        ) : (
          <>
            <section>
              <h2>Economic Status Scores</h2>
              <div className="score-grid">
                {metrics.map((m) => (
                  <ScoreCard
                    key={m}
                    metric={m}
                    score={scores[m]}
                    selected={selected === m}
                    onSelect={setSelected}
                  />
                ))}
              </div>
            </section>

            <section>
              {seriesLoading ? (
                <Loading label="Loading history…" />
              ) : (
                selected && <RiskChart metric={selected} scores={series} />
              )}
            </section>

            <AlertsManager
              api={api}
              metrics={metrics}
              userEmail={user?.email}
              onError={handleAuthError}
            />
          </>
        )}
      </main>
    </div>
  );
}
