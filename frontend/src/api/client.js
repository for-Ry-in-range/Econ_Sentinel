/**
 * API client for the REST API (API Gateway + Lambda function)
 *
 * Every request has a Cognito ID token in the header, which the API Gateway Cognito
 * authorizer uses to validate.
 *
 * Endpoints:
 *   GET    /metrics
 *   GET    /scores/latest?metric=
 *   GET    /scores?metric=&start=YYYY-MM-DD&end=YYYY-MM-DD
 *   GET    /alerts
 *   PUT    /alerts            body { metric, threshold, enabled, email }
 *   DELETE /alerts/{metric}
 */

import { config } from '../config.js';

/** Raised when the API returns 401, so the UI can redirect to login. */
export class UnauthorizedError extends Error {
  constructor(message = 'Session expired. Please sign in again.') {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

/**
 * Create an API client along with a token getter
 * @param {() => Promise<string|null>} getIdToken
 */
export function createApiClient(getIdToken) {

  // This function is used by all the API client's returned functions
  async function request(method, path, { query, body } = {}) {
    const token = await getIdToken();
    if (!token) throw new UnauthorizedError();

    const url = new URL(config.apiUrl + path);
    if (query) {
      for (const [k, v] of Object.entries(query)) {
        if (v !== undefined && v !== null && v !== '') {
        }
          url.searchParams.set(k, v);
      }
    }

    const res = await fetch(url.toString(), {
      method,
      headers: {
        Authorization: token,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 || res.status === 403) {
      throw new UnauthorizedError();
    }

    const text = await res.text();
    const data = text ? safeJson(text) : null;

    if (!res.ok) {
      const message = data?.error || `Request failed (${res.status})`;
      const err = new Error(message);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  return {
    
    async getMetrics() {
      const data = await request('GET', '/metrics');
      return data?.metrics || [];
    },

    /** Latest risk-score for a metric, or null if none yet. */
    async getLatestScore(metric) {
      try {
        return await request('GET', '/scores/latest', { query: { metric } });
      } catch (err) {
        if (err.status === 404) return null;
        throw err;
      }
    },

    /** Time series of scores (eg. 30 days of scores) */
    async getTimeSeries(metric, start, end) {
      const data = await request('GET', '/scores', {
        query: { metric, start, end },
      });
      return data?.scores || [];
    },

    /** The signed-in user's alert rules */
    async getAlerts() {
      const data = await request('GET', '/alerts');
      return data?.alerts || [];
    },

    /** Create or update an alert rule. */
    async putAlert({ metric, threshold, enabled, email }) {
      return request('PUT', '/alerts', {
        body: { metric, threshold, enabled, email },
      });
    },

    /** Delete an alert rule by metric. */
    async deleteAlert(metric) {
      return request('DELETE', `/alerts/${encodeURIComponent(metric)}`);
    },
  };
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
