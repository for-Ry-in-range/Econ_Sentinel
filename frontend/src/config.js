/**
 * Runtime configuration
 */

export const config = {
  apiUrl: stripTrailingSlash(import.meta.env.VITE_API_URL || ''),
  userPoolId: import.meta.env.VITE_USER_POOL_ID || '',
  userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID || '',
  region: import.meta.env.VITE_AWS_REGION || '',
};

function stripTrailingSlash(url) {
  return url.endsWith('/') ? url.slice(0, -1) : url;
}

/** True only when every required value is present. */
export function isConfigured() {
  return Boolean(
    config.apiUrl && config.userPoolId && config.userPoolClientId
  );
}

/**
 * Friendly display metadata for known metric keys (from ingestion/config.py).
 * Unknown metrics fall back to a title-cased key via metricLabel().
 */
export const METRIC_META = {
  initial_jobless_claims: {
    label: 'Initial Jobless Claims',
    description: 'Weekly U.S. initial unemployment insurance claims',
    unit: 'claims',
  },
  yield_curve_10y2y: {
    label: '10Y-2Y Yield Spread',
    description: '10-Year minus 2-Year Treasury yield spread (negative = inverted curve)',
    unit: 'pts',
  },
  port_la_vessel_queue: {
    label: 'Port of LA Vessel Queue',
    description: 'Vessels waiting in the Port of Los Angeles queue',
    unit: 'vessels',
  },
};

export function metricLabel(metric) {
  if (METRIC_META[metric]) return METRIC_META[metric].label;
  return metric
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function metricDescription(metric) {
  return METRIC_META[metric]?.description || '';
}

/**
 * Severity → presentation, aligned with backend RiskCalculator thresholds:
 * normal (<5%), warning (5-15%), critical (>15%).
 */
export const SEVERITY_META = {
  normal: { label: 'Normal', color: '#2e7d32', bg: '#e8f5e9' },
  warning: { label: 'Warning', color: '#b26a00', bg: '#fff4e0' },
  critical: { label: 'Critical', color: '#c62828', bg: '#fdecea' },
};

export function severityMeta(severity) {
  return SEVERITY_META[severity] || SEVERITY_META.normal;
}
