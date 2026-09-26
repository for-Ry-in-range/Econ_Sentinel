import { metricLabel, metricDescription, severityMeta } from '../config.js';

function formatNumber(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  const num = Number(n);
  return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatPct(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  const num = Number(n);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}


// One metric tile card

export default function ScoreCard({ metric, score, selected, onSelect }) {
  const sev = severityMeta(score?.severity);
  const hasData = Boolean(score);

  return (
    <button
      type="button"
      className={`score-card${selected ? ' selected' : ''}`}
      onClick={() => onSelect(metric)}
      style={{ borderTopColor: hasData ? sev.color : '#cfd4dc' }}
      aria-pressed={selected}
    >
      <div className="score-card-head">
        <span className="score-card-title">{metricLabel(metric)}</span>
        {hasData && (
          <span
            className="severity-badge"
            style={{ color: sev.color, background: sev.bg }}
          >
            {sev.label}
          </span>
        )}
      </div>
      <p className="score-card-desc">{metricDescription(metric)}</p>

      {hasData ? (
        <div className="score-card-stats">
          <div className="stat">
            <span className="stat-value">{formatNumber(score.value)}</span>
            <span className="stat-label">Current</span>
          </div>
          <div className="stat">
            <span className="stat-value" style={{ color: sev.color }}>
              {formatPct(score.pct_change)}
            </span>
            <span className="stat-label">vs 30d avg</span>
          </div>
          <div className="stat">
            <span className="stat-value">{formatNumber(score.risk_score)}</span>
            <span className="stat-label">Risk score</span>
          </div>
        </div>
      ) : (
        <div className="score-card-empty">No data yet</div>
      )}
    </button>
  );
}
