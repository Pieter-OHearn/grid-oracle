import type { CSSProperties, ReactNode } from 'react';
import type { PublishedRun } from './contract';
import type { QueryState } from './query';
import { fieldTotal, probability } from './format';
import { Panel } from '../design-system/Panel';

export function Notice({
  title,
  children,
  error = false,
}: {
  title: string;
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div className="go-notice" role={error ? 'alert' : 'status'}>
      <h2>{title}</h2>
      {children}
    </div>
  );
}
export function QueryNotice({ query }: { query: QueryState<unknown> & { retry: () => void } }) {
  if (query.state === 'ready') return null;
  if (query.state === 'loading')
    return (
      <Notice title="Loading selected data">
        <p>No values are shown until this request is ready.</p>
      </Notice>
    );
  return (
    <Notice title="Could not load data" error>
      <p>{query.message}</p>
      {query.retryable && <button onClick={query.retry}>Retry</button>}
    </Notice>
  );
}
export function ForecastContext({ run }: { run: PublishedRun }) {
  const time = (value: string | null) =>
    value === null
      ? 'Unknown'
      : new Date(value).toLocaleString(undefined, { timeZone: 'UTC' }) + ' UTC';
  const labels = {
    verified_as_of_cutoff: 'Verified as of cutoff',
    source_late: 'Source late',
    stale: 'Stale snapshot',
    unknown: 'Cannot verify freshness',
  };
  return (
    <div className="go-context">
      <strong>Published snapshot · {run.provenance} provenance</strong>
      <dl>
        <div>
          <dt>Input cutoff</dt>
          <dd>{time(run.freshness.input_cutoff_at)}</dd>
        </div>
        <div>
          <dt>Issued</dt>
          <dd>{time(run.freshness.issued_at)}</dd>
        </div>
        <div>
          <dt>Freshness</dt>
          <dd>{labels[run.freshness.state]}</dd>
        </div>
        <div>
          <dt>Coverage</dt>
          <dd>
            {run.coverage.state} · {run.coverage.available ?? 'Unknown'}/
            {run.coverage.expected ?? 'Unknown'}
          </dd>
        </div>
      </dl>
      {run.freshness.reason && <p>{run.freshness.reason}</p>}
      <p>Later information never rewrites this snapshot.</p>
    </div>
  );
}
export function FieldTable({ run, limit }: { run: PublishedRun; limit?: number }) {
  const known = run.entries
    .filter((e) => e.win_probability !== null)
    .sort((a, b) => b.win_probability! - a.win_probability!);
  const unknown = run.entries.filter((e) => e.win_probability === null);
  const shown = [...(limit ? known.slice(0, limit) : known), ...unknown];
  const total =
    run.coverage.state === 'complete' &&
    run.coverage.expected === run.entries.length &&
    run.coverage.available === run.entries.length
      ? fieldTotal(run.entries)
      : null;
  const incomplete = unknown.length > 0 || run.coverage.state !== 'complete';
  if (!run.entries.length)
    return (
      <Notice title="No entries available">
        <p>No ranking or field total can be calculated.</p>
      </Notice>
    );
  return (
    <Panel
      title="Win probabilities"
      note="Ordered by win chance, not predicted finishing position."
    >
      <p className="go-scroll-hint">Scroll horizontally for all probability columns.</p>
      <div
        className="go-table-wrap"
        tabIndex={0}
        role="region"
        aria-label="Published probabilities; scroll horizontally on small screens"
      >
        <table className="go-timing">
          <caption>
            {run.season} · {run.horizon === 'pre_weekend' ? 'Pre-weekend' : 'After qualifying'} ·{' '}
            {run.entries.length} entries · Published snapshot
            {incomplete ? ' · Partial field, entries unranked' : ''}
          </caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Driver / team</th>
              <th scope="col">Win chance</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((entry, index) => (
              <tr key={entry.entry_key}>
                <td className="go-number">
                  {incomplete ? 'Unranked' : String(index + 1).padStart(2, '0')}
                </td>
                <th scope="row">
                  <div
                    className="go-driver"
                    style={
                      {
                        '--go-team': entry.team_color ?? 'var(--go-control-border)',
                      } as CSSProperties
                    }
                  >
                    <span>{entry.driver_name ?? 'Driver name unavailable'}</span>
                    <small>{entry.team_name ?? 'Historical team name unavailable'}</small>
                  </div>
                </th>
                <td className="go-number">{probability(entry.win_probability)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="go-field-note">
        <span>
          Full field: {probability(total)} · {run.entries.length} entries
        </span>
        {total !== null && Math.abs(total - 1) > 0.00001 && (
          <span>Published probabilities do not sum to 100%; no normalization applied.</span>
        )}
        {limit && <span>{run.entries.length - shown.length} additional entries in full field</span>}
      </div>
    </Panel>
  );
}
