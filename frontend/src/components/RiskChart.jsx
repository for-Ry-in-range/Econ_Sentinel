import { useMemo } from 'react';  // use memoization (to minimize recalculations)
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { metricLabel } from '../config.js';

/**
 * Time-series chart for a single metric. `scores` is the array returned by
 * GET /scores (newest first); we sort ascending for the x-axis and plot the
 * raw value and the 0-100 risk score on separate y-axes.
 */
export default function RiskChart({ metric, scores }) {
  const data = useMemo(() => {
    return [...scores]
      .sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)))
      .map((s) => ({
        date: String(s.timestamp).slice(0, 10),
        value: Number(s.value),
        risk_score: Number(s.risk_score),
      }));
  }, [scores]);

  if (data.length === 0) {
    return (
      <div className="chart-empty">
        No history for {metricLabel(metric)} in the selected range yet.
      </div>
    );
  }

  return (
    <div className="chart-wrap">
      <h3 className="chart-title">{metricLabel(metric)} — last 30 days</h3>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eceff3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={24} />
          <YAxis
            yAxisId="value"
            tick={{ fontSize: 12 }}
            width={64}
            domain={['auto', 'auto']}
          />
          <YAxis
            yAxisId="risk"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 12 }}
            width={40}
          />
          <Tooltip />
          <Legend />
          <Line
            yAxisId="value"
            type="monotone"
            dataKey="value"
            name="Value"
            stroke="#1f6feb"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="risk"
            type="monotone"
            dataKey="risk_score"
            name="Risk score"
            stroke="#c62828"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
