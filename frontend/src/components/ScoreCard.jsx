import { metricLabel, metricDescription, severityMeta, isLevelBased, isScoreBased } from '../config.js';

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

function formatPts(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  const num = Number(n);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)} pts`;
}


// Displays which components the composite index is influenced by (weight * score)
function CompositeBreakdown({ components }) {
  if (!Array.isArray(components) || components.length === 0) {
    return null;
  } 
  const ranked = [...components].sort(
    (a, b) => Number(b.weight) * Number(b.risk_score) - Number(a.weight) * Number(a.risk_score)
  );
  return (
    <span className="score-card-components">
      {ranked.map((c) => (
        <span className="component-row" key={c.metric}>
          <span className="component-name">
            {metricLabel(c.metric)}
            {Number(c.weight) !== 1 && (
              <span className="component-weight"> ×{formatNumber(c.weight)}</span>
            )}
          </span>
          <span className="component-score">{formatNumber(c.risk_score)}</span>
        </span>
      ))}
    </span>
  );
}


// One metric tile card

export default function ScoreCard({ metric, score, selected, onSelect }) {
  const sev = severityMeta(score?.severity);
  const hasData = Boolean(score);
  const levelBased = isLevelBased(metric); // Is based on value instead of percent change
  const scoreBased = isScoreBased(metric); // For composite score (cause it's already a 0-100 score)

  const avgDiff =
    hasData && score.moving_avg_30d !== undefined && score.moving_avg_30d !== null
      ? Number(score.value) - Number(score.moving_avg_30d)
      : null;

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

      {hasData && scoreBased ? ( // If there's data and it's a composite score score card
        <>
          <div className="score-card-stats">
            <div className="stat">
              <span className="stat-value" style={{ color: sev.color }}>
                {formatNumber(score.risk_score)}
                <span className="stat-outof"> / 100</span>
              </span>
              <span className="stat-label">Stress score</span>
            </div>
          </div>
          <CompositeBreakdown components={score.components} />
        </>
      ) : hasData ? (  // if not a composite score score card
        <div className="score-card-stats">
          <div className="stat">
            <span className="stat-value">{formatNumber(score.value)}</span>
            <span className="stat-label">Current</span>
          </div>
          <div className="stat">
            <span className="stat-value" style={{ color: sev.color }}>
              {levelBased ? formatPts(avgDiff) : formatPct(score.pct_change)}
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
