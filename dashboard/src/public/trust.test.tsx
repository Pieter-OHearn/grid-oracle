import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MetricTable, CorrectionHistory, Methodology } from './Trust';
import { metricValue, probabilityDelta } from './trustFormat';
import type { PerformanceMetric } from './contract';

const metric: PerformanceMetric = {
  key: 'winner_hit',
  label: 'Winner pick hit rate',
  outcome: 'first predicted entrant is official winner',
  value: 0,
  unit: 'fraction',
  observations: 1,
};
describe('Public trust copy and exact stored values', () => {
  it('uses signed percentage points with honest displayed precision and missingness', () => {
    expect(probabilityDelta(0.2, 0.25)).toBe('+5.0 percentage points');
    expect(probabilityDelta(0.25, 0.2)).toBe('−5.0 percentage points');
    expect(probabilityDelta(0, 0)).toBe('No change at displayed precision');
    expect(probabilityDelta(null, 0)).toBe('Not available');
    expect(probabilityDelta(0, null)).toBe('Not available');
    expect(probabilityDelta(0.20001, 0.2)).toBe('No change at displayed precision');
  });
  it('names score outcomes, preserves zero and shows unavailable metrics separately', () => {
    expect(metricValue(metric)).toBe('0%');
    expect(metricValue({ ...metric, value: null, observations: 0 })).toBe('Not available');
    const html = renderToStaticMarkup(
      <MetricTable metrics={[metric]} caption="Stored result revision 1" />,
    );
    expect(html).toContain('Winner pick hit rate');
    expect(html).toContain(metric.outcome);
    expect(html).toContain('0%');
    expect(html).toContain('scope="row"');
  });
  it('shows an unevaluated correction without reusing an earlier score', () => {
    const html = renderToStaticMarkup(
      <CorrectionHistory
        data={{
          season: 2023,
          event_id: 1,
          event_name: 'Test event',
          round: 1,
          horizon: 'pre_weekend',
          run_id: 'original',
          status: 'stored_evaluation',
          corrections: [
            {
              revision: 2,
              recorded_at: '2023-01-01T00:00:00Z',
              official: true,
              change: 'Result correction recorded',
              evaluations: [],
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Result revision 2');
    expect(html).toContain('No public evaluation for this revision');
    expect(html).not.toContain('0%');
  });
  it('describes set membership separately from exact position and withholds unsupported outputs', () => {
    const html = renderToStaticMarkup(<Methodology />);
    expect(html).toContain('Exact-position accuracy');
    expect(html).toContain('regardless of order');
    expect(html).toContain('out-of-sample relative to fitting');
    expect(html).toContain('no retirement, DNS or DSQ mechanism');
    expect(html).toContain('They are withheld');
    expect(html).toContain('verified model-specific public card is unavailable');
  });
});
