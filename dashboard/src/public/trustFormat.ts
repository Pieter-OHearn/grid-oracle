import type { PerformanceMetric } from './contract';
import { probability } from './format';

export const horizonName = (horizon: string) =>
  horizon === 'pre_weekend' ? 'Pre-weekend' : 'After qualifying';
export const number = (value: number | null) =>
  value === null ? 'Not available' : value.toFixed(6);
export const metricValue = (metric: PerformanceMetric) =>
  metric.value === null
    ? 'Not available'
    : metric.unit === 'fraction'
      ? probability(metric.value)
      : number(metric.value);
export function probabilityDelta(before: number | null, after: number | null) {
  if (before === null || after === null) return 'Not available';
  const delta = (after - before) * 100;
  if (Math.abs(delta) < 0.05) return 'No change at displayed precision';
  return `${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)} percentage points`;
}
