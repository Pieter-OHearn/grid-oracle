import type { CSSProperties, ReactNode } from 'react';
import { change, horizonLabels, percentage, sampleTiming, total } from './sample';
import type { DataState, Entry, Horizon, Journey } from './sample';

export function Panel({
  title,
  children,
  note,
}: {
  title: string;
  children: ReactNode;
  note?: string;
}) {
  return (
    <section className="go-panel">
      <header className="go-panel-heading">
        <h2>{title}</h2>
        {note && <p className="go-muted">{note}</p>}
      </header>
      {children}
    </section>
  );
}
export function SampleNotice() {
  return (
    <p className="go-sample">Design reference · Synthetic sample data · Not a real forecast</p>
  );
}
export function HorizonControl({
  value,
  onChange,
}: {
  value: Horizon;
  onChange: (value: Horizon) => void;
}) {
  return (
    <div className="go-horizons" role="group" aria-label="Forecast horizon">
      {(['pre', 'post'] as const).map((h, i) => (
        <button key={h} type="button" aria-pressed={h === value} onClick={() => onChange(h)}>
          <span className="go-number">0{i + 1}</span> {horizonLabels[h]}
        </button>
      ))}
    </div>
  );
}
export function ForecastContext({
  horizon,
  unknown = false,
}: {
  horizon: Horizon;
  unknown?: boolean;
}) {
  const timing = sampleTiming[horizon];
  return (
    <div className="go-context">
      <strong>{horizonLabels[horizon]} · Sample run</strong>
      <dl>
        <div>
          <dt>Input cutoff</dt>
          <dd>{unknown ? 'Unknown — source timestamps missing' : timing.cutoff}</dd>
        </div>
        <div>
          <dt>Issued</dt>
          <dd>{unknown ? 'Unknown' : timing.issued}</dd>
        </div>
        <div>
          <dt>Freshness</dt>
          <dd>{unknown ? 'Cannot verify freshness' : timing.freshness}</dd>
        </div>
      </dl>
      <p>Sample snapshot only. Later information never rewrites an earlier forecast.</p>
    </div>
  );
}
const stateCopy: Record<Exclude<DataState, 'ready'>, { title: string; copy: string }> = {
  loading: {
    title: 'Loading sample forecast',
    copy: 'Waiting for the selected horizon. No probabilities shown until the complete snapshot is ready.',
  },
  unavailable: {
    title: 'Forecast unavailable',
    copy: 'No published run for this horizon. After qualifying requires verified final qualifying and grid data before race start.',
  },
  error: {
    title: 'Could not load forecast',
    copy: 'The request failed. This differs from a forecast that has not been published.',
  },
  unknown: {
    title: 'Some data is unknown',
    copy: 'Missing probabilities and timestamps stay unknown. They are never converted to zero; field totals and changes cannot be verified.',
  },
  empty: {
    title: 'No entries available',
    copy: 'This sample has no event entries. No ranking or total can be calculated.',
  },
};
const journeyStateCopy = {
  scorecard: {
    loading: {
      title: 'Loading sample scorecard',
      copy: 'Waiting for the selected horizon and provenance cohort. No performance metrics shown yet.',
    },
    unavailable: {
      title: 'Scorecard unavailable',
      copy: 'No validated evaluation artifact for this horizon and cohort. Absence is not a zero loss.',
    },
    error: {
      title: 'Could not load scorecard',
      copy: 'The scorecard request failed. Retry rather than interpreting this as missing evaluation evidence.',
    },
    unknown: {
      title: 'Performance is unknown',
      copy: 'Cohort coverage, calibration and uncertainty are unverified. No accuracy claim is made.',
    },
    empty: {
      title: 'No evaluated races',
      copy: 'This cohort has no eligible evaluated races. Loss and calibration cannot be calculated.',
    },
  },
  archive: {
    loading: {
      title: 'Loading sample archive',
      copy: 'Waiting for the event index. No event coverage is inferred while loading.',
    },
    unavailable: {
      title: 'Archive unavailable',
      copy: 'No archive is published for this example selection. This does not imply a season had no races.',
    },
    error: {
      title: 'Could not load archive',
      copy: 'The archive request failed. Retry rather than showing an empty calendar.',
    },
    unknown: {
      title: 'Archive coverage unknown',
      copy: 'Snapshot availability and provenance cannot be verified. Synthetic examples remain labelled.',
    },
    empty: {
      title: 'No archive events',
      copy: 'No events in this example index. No historical coverage claim is made.',
    },
  },
};
export function DataNotice({
  state,
  onRetry,
  journey = 'race',
}: {
  state: DataState;
  onRetry: () => void;
  journey?: Journey;
}) {
  if (state === 'ready') return null;
  const copy =
    journey === 'scorecard' || journey === 'archive'
      ? journeyStateCopy[journey][state]
      : stateCopy[state];
  return (
    <div className="go-notice" role={state === 'error' ? 'alert' : 'status'}>
      <h2>{copy.title}</h2>
      <p>{copy.copy}</p>
      {state === 'error' && (
        <button type="button" onClick={onRetry}>
          Retry sample
        </button>
      )}
    </div>
  );
}
function TimingRow({
  entry,
  horizon,
  comparison,
  rank,
}: {
  entry: Entry;
  horizon: Horizon;
  comparison: boolean;
  rank: string;
}) {
  return (
    <tr>
      <td className="go-number">{rank}</td>
      <th scope="row">
        <div className="go-driver" style={{ '--go-team': entry.color } as CSSProperties}>
          <span>{entry.name}</span>
          <small>{entry.team}</small>
        </div>
      </th>
      {comparison ? (
        <>
          <td className="go-number">{percentage(entry.pre)}</td>
          <td className="go-number">{percentage(entry.post)}</td>
        </>
      ) : (
        <td className="go-number">{percentage(entry[horizon])}</td>
      )}
      <td className="go-number">
        {comparison || horizon === 'post' ? change(entry) : 'Not applicable'}
      </td>
    </tr>
  );
}
export function TimingTable({
  entries,
  horizon,
  comparison = false,
  limit,
}: {
  entries: Entry[];
  horizon: Horizon;
  comparison?: boolean;
  limit?: number;
}) {
  const unknown = entries.filter((entry) => entry[horizon] === null);
  const known = entries
    .filter((entry) => entry[horizon] !== null)
    .sort((a, b) => b[horizon]! - a[horizon]!);
  const shownKnown = limit ? known.slice(0, limit) : known;
  // Missing entries stay visible outside the known subset and never receive a field rank.
  const shown = [...shownKnown, ...unknown];
  const incomplete = unknown.length > 0;
  const fieldTotal = total(entries, horizon);
  const rest =
    fieldTotal === null
      ? null
      : entries
          .filter((entry) => !shown.includes(entry))
          .reduce((sum, entry) => sum + (entry[horizon] ?? 0), 0);
  return (
    <>
      <p className="go-scroll-hint">Scroll the table horizontally for all probability columns.</p>
      <div
        className="go-table-wrap"
        tabIndex={0}
        role="region"
        aria-label="Sample probabilities table; scroll horizontally on small screens"
      >
        <table className="go-timing">
          <caption>
            Synthetic{' '}
            {comparison ? 'horizon comparison' : `${horizonLabels[horizon]} win probabilities`} ·{' '}
            {entries.length} entries · Not a forecast ·{' '}
            {incomplete
              ? 'Incomplete field · Known probabilities only; unknown entries are unranked'
              : 'Ordered by win chance, not finishing position'}
          </caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Driver / team</th>
              {comparison ? (
                <>
                  <th scope="col">Pre-weekend</th>
                  <th scope="col">After qualifying</th>
                </>
              ) : (
                <th scope="col">Win chance</th>
              )}
              <th scope="col">Change (pp)</th>
            </tr>
          </thead>
          <tbody>
            {incomplete && (
              <tr>
                <th scope="rowgroup" colSpan={comparison ? 5 : 4}>
                  Known probabilities · partial field, no field ranking
                </th>
              </tr>
            )}
            {shownKnown.map((entry, index) => (
              <TimingRow
                key={entry.id}
                entry={entry}
                horizon={horizon}
                comparison={comparison}
                rank={incomplete ? 'Unranked' : String(index + 1).padStart(2, '0')}
              />
            ))}
          </tbody>
          {incomplete && (
            <tbody>
              <tr>
                <th scope="rowgroup" colSpan={comparison ? 5 : 4}>
                  Unknown probabilities · not ranked
                </th>
              </tr>
              {unknown.map((entry) => (
                <TimingRow
                  key={entry.id}
                  entry={entry}
                  horizon={horizon}
                  comparison={comparison}
                  rank="Unranked"
                />
              ))}
            </tbody>
          )}
        </table>
      </div>
      <div className="go-field-note">
        <span>
          Full field: {fieldTotal === null ? 'Unknown total' : `${fieldTotal}%`} · {entries.length}{' '}
          entries
        </span>
        {limit && (
          <span>
            Other {entries.length - shown.length} drivers: {percentage(rest)} combined
          </span>
        )}
        <span>pp = percentage points, not relative percent</span>
      </div>
    </>
  );
}
