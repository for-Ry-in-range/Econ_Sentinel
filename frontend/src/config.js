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
  inflation_rate_cpi: {
    label: 'Inflation (CPI)',
    description: 'Consumer Price Index for All Urban Consumers',
    unit: 'index',
  },
  ppi_all_commodities: {
    label: 'Producer Prices (PPI)',
    description: 'Producer Price Index, All Commodities',
    unit: 'index',
  },
  unemployment_rate: {
    label: 'Unemployment Rate',
    description: 'U.S. civilian unemployment rate',
    unit: '%',
  },
  freight_cost_index: {
    label: 'Freight Cost Index',
    description: 'PPI: Freight Transportation',
    unit: 'index',
  },
  freight_cost_trucking: {
    label: 'Trucking Cost',
    description: 'PPI: General Freight Trucking',
    unit: 'index',
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
