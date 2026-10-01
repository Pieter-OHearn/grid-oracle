import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { FieldTable, QueryNotice } from './components';
import { fieldTotal, probability } from './format';
import { switchSeasonPath } from './navigation';
import { QueryCache } from './query';
import type { PublicEntry, PublishedRun } from './contract';

const entry: PublicEntry = {
  entry_key: 'entry:1',
  driver_name: 'Historical driver',
  team_name: 'Historical team',
  team_color: null,
  win_probability: null,
};
const run: PublishedRun = {
  run_id: 'published',
  season: 2022,
  event_id: 1,
  horizon: 'pre_weekend',
  published_at: '2022-05-01T10:00:00Z',
  provenance: 'verified',
  freshness: {
    state: 'verified_as_of_cutoff',
    input_cutoff_at: null,
    issued_at: null,
    source_available_at: null,
    reason: null,
  },
  coverage: { state: 'empty', available: 0, expected: 0, reason: null },
  entries: [],
};
const flush = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0));
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('Public data semantics and URLs', () => {
  it('keeps missing/zero/empty distinct and never fabricates totals', () => {
    expect(probability(null)).toBe('Unknown');
    expect(probability(0)).toBe('0%');
    expect(fieldTotal([])).toBeNull();
    expect(fieldTotal([entry])).toBeNull();
    const html = renderToStaticMarkup(<FieldTable run={run} />);
    expect(html).toContain('No entries available');
    expect(html).not.toMatch(/NaN|0%/);
  });
  it('retains unknown entries in a leading subset and suppresses unsupported ranks', () => {
    const entries = [
      entry,
      ...Array.from({ length: 22 }, (_, i) => ({
        ...entry,
        entry_key: `entry:${i + 2}`,
        win_probability: 1 / 22,
      })),
    ];
    const html = renderToStaticMarkup(
      <FieldTable
        run={{
          ...run,
          entries,
          coverage: { state: 'partial', available: 22, expected: 23, reason: null },
        }}
        limit={5}
      />,
    );
    expect(html).toContain('Unranked');
    expect(html).toContain('Unknown');
    expect(html).toContain('23 entries');
    expect(html).not.toContain('NaN');
  });
  it('renders API errors as retryable alerts and loading without percentages', () => {
    const error = renderToStaticMarkup(
      <QueryNotice
        query={{ state: 'error', message: 'API unavailable', retryable: true, retry: () => {} }}
      />,
    );
    expect(error).toContain('role="alert"');
    expect(error).toContain('Retry');
    const loading = renderToStaticMarkup(
      <QueryNotice query={{ state: 'loading', retry: () => {} }} />,
    );
    expect(loading).toContain('Loading selected data');
    expect(loading).not.toContain('%');
  });
  it('switches every journey without reusing another season event ID', () => {
    expect(switchSeasonPath('/seasons/2022/events/7/field', 2026, '?horizon=post_qualifying')).toBe(
      '/seasons/2026/weekend?horizon=post_qualifying&view=field',
    );
    expect(switchSeasonPath('/seasons/2022/events/7/sessions', 2026, '')).toBe(
      '/seasons/2026/weekend?view=sessions',
    );
    for (const page of ['events', 'record', 'methodology', 'sources'])
      expect(switchSeasonPath(`/seasons/2022/${page}`, 2026, '')).toBe(`/seasons/2026/${page}`);
  });
});

describe('Shared query lifecycle', () => {
  it('deduplicates requests, caches reads and keeps season keys independent', async () => {
    const transport = vi.fn(async () => response({ seasons: [] }));
    const cache = new QueryCache(transport);
    const a = cache.subscribe('/2022', 'SeasonIndex', () => {});
    const b = cache.subscribe('/2022', 'SeasonIndex', () => {});
    await flush();
    expect(transport).toHaveBeenCalledTimes(1);
    expect(cache.snapshot('/2022').state).toBe('ready');
    expect(cache.snapshot('/2026').state).toBe('loading');
    a();
    b();
    await flush();
    const c = cache.subscribe('/2022', 'SeasonIndex', () => {});
    expect(transport).toHaveBeenCalledTimes(1);
    c();
  });
  it('cancels only after the last consumer leaves and ignores late responses', async () => {
    let resolve!: (response: Response) => void;
    let signal: AbortSignal | undefined;
    const transport = vi.fn((_url, options) => {
      signal = options?.signal as AbortSignal;
      return new Promise<Response>((r) => {
        resolve = r;
      });
    });
    const cache = new QueryCache(transport);
    const a = cache.subscribe('/old', 'SeasonIndex', () => {});
    const b = cache.subscribe('/old', 'SeasonIndex', () => {});
    a();
    await flush();
    expect(signal?.aborted).toBe(false);
    b();
    await flush();
    expect(signal?.aborted).toBe(true);
    resolve(response({ seasons: [] }));
    await flush();
    expect(cache.snapshot('/old').state).toBe('loading');
  });
  it('distinguishes absent forecasts, malformed contracts and retryable transport errors', async () => {
    const transport = vi.fn(async () =>
      response({ state: 'unavailable', reason: 'no_published_forecast', run: null }),
    );
    const cache = new QueryCache(transport);
    const unsubscribe = cache.subscribe('/forecast', 'ForecastSelection', () => {});
    await flush();
    expect(cache.snapshot('/forecast').state).toBe('ready');
    transport.mockImplementationOnce(async () =>
      response({ state: 'published', run: null, reason: null }),
    );
    cache.retry('/forecast', 'ForecastSelection');
    await flush();
    expect(cache.snapshot('/forecast').state).toBe('error');
    transport.mockImplementationOnce(async () =>
      response(
        { error: { code: 'api_unavailable', message: 'Service unavailable', retryable: true } },
        503,
      ),
    );
    cache.retry('/forecast', 'ForecastSelection');
    await flush();
    expect(cache.snapshot('/forecast')).toEqual({
      state: 'error',
      message: 'Service unavailable',
      retryable: true,
    });
    cache.retry('/forecast', 'ForecastSelection');
    await flush();
    expect(cache.snapshot('/forecast').state).toBe('ready');
    unsubscribe();
  });
});
