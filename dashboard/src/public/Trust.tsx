import { useState } from 'react';
import type { ReactNode } from 'react';
import type {
  EventPerformance,
  HistoricalPerformance,
  LivePerformance,
  PerformanceMetric,
  PublishedRun,
  RunIndex,
} from './contract';
import { useQuery } from './query';
import { Notice, QueryNotice, ForecastContext } from './components';
import { Panel } from '../design-system/Panel';
import { probability } from './format';

import { horizonName, number, metricValue, probabilityDelta } from './trustFormat';

function TableRegion({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="go-table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}
export function MetricTable({
  metrics,
  caption,
}: {
  metrics: PerformanceMetric[];
  caption: string;
}) {
  return (
    <TableRegion label={caption}>
      <table className="go-timing go-trust-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Metric / outcome</th>
            <th scope="col">Stored value</th>
            <th scope="col">Observed races</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.key}>
              <th scope="row">
                {m.label}
                <small className="go-metric-outcome">{m.outcome}</small>
              </th>
              <td className="go-number">{metricValue(m)}</td>
              <td>{m.observations ?? 'Unknown'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableRegion>
  );
}
export function DriverDetail({ run }: { run: PublishedRun }) {
  const [entryKey, setEntryKey] = useState(run.entries[0]?.entry_key ?? '');
  const entry = run.entries.find((e) => e.entry_key === entryKey);
  return (
    <Panel
      title="Driver detail"
      note="Stored winner probability; no per-driver causal attribution is available."
    >
      <div className="go-panel-body">
        <label>
          Driver{' '}
          <select
            aria-label="Driver"
            value={entryKey}
            onChange={(e) => setEntryKey(e.target.value)}
          >
            {run.entries.map((e) => (
              <option key={e.entry_key} value={e.entry_key}>
                {e.driver_name ?? 'Driver name unavailable'}
              </option>
            ))}
          </select>
        </label>
        {entry && (
          <>
            <h3>{entry.driver_name ?? 'Driver name unavailable'}</h3>
            <p>{entry.team_name ?? 'Historical team name unavailable'}</p>
            <p>
              Official race win chance: <strong>{probability(entry.win_probability)}</strong>. This
              is one outcome across the original {run.entries.length}-entry field.
            </p>
            <p>
              Probability describes uncertainty. It does not predict an exact finishing position or
              guarantee a win. Official podium, top-ten, points, retirement and position
              distributions are not available for this run.
            </p>
          </>
        )}
        <p>
          {run.horizon === 'pre_weekend'
            ? 'This horizon excludes current-weekend qualifying.'
            : 'This horizon permits verified qualifying information before race start.'}{' '}
          Associations in standings, prior classified results or qualifying can inform a model; they
          do not establish why a driver will finish in a particular position. The public record does
          not provide a verified per-feature explanation.
        </p>
      </div>
    </Panel>
  );
}
export function RunComparison({ season, eventId }: { season: number; eventId: number }) {
  const query = useQuery<RunIndex>(`/api/v1/seasons/${season}/events/${eventId}/runs`, 'RunIndex');
  const [beforeId, setBeforeId] = useState<string | null>(null);
  const [afterId, setAfterId] = useState<string | null>(null);
  if (query.state !== 'ready') return <QueryNotice query={query} />;
  const runs = query.data.runs;
  const before =
    beforeId === null
      ? runs.find((r) => r.horizon === 'pre_weekend')
      : runs.find((r) => r.run_id === beforeId);
  const after =
    afterId === null
      ? runs.find((r) => r.horizon === 'post_qualifying')
      : runs.find((r) => r.run_id === afterId);
  const keys = [
    ...new Set([
      ...(before?.entries ?? []).map((e) => e.entry_key),
      ...(after?.entries ?? []).map((e) => e.entry_key),
    ]),
  ];
  const sameField =
    !!before &&
    !!after &&
    before.entries.length === after.entries.length &&
    before.entries.every((e) => after.entries.some((a) => a.entry_key === e.entry_key));
  return (
    <Panel
      title="Horizon and revision comparison"
      note="Change = comparison snapshot minus reference snapshot, in percentage points."
    >
      <div className="go-panel-body">
        <p>
          Each selection is an immutable approved run. The publication contract currently permits
          one run per horizon; unpublished revisions remain unavailable. A horizon change is not
          evidence that qualifying caused a probability change.
        </p>
        <div className="go-comparison-controls">
          {[
            ['Reference', before?.run_id ?? '', setBeforeId],
            ['Comparison', after?.run_id ?? '', setAfterId],
          ].map(([label, id, setter]) => (
            <label key={label as string}>
              {label as string}{' '}
              <select
                aria-label={label as string}
                value={id as string}
                onChange={(e) => (setter as (value: string) => void)(e.target.value)}
              >
                <option value="">Not available</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {horizonName(r.horizon)} · {r.freshness.issued_at ?? 'Issue time unknown'} ·{' '}
                    {r.run_id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        {before && <ForecastContext run={before} />}
        {after && <ForecastContext run={after} />}
        {!before || !after ? (
          <p>
            Both selected snapshots are required for a win-probability change. Missing publication
            is not zero probability.
          </p>
        ) : !sameField ? (
          <p>
            The entry field changed. Win-probability deltas are not comparable; original
            probabilities remain visible without renormalization.
          </p>
        ) : null}
      </div>
      {keys.length > 0 && (
        <TableRegion label="Full-field win probability comparison">
          <table className="go-timing go-trust-table">
            <caption>Official race win chance · full field · original snapshots</caption>
            <thead>
              <tr>
                <th scope="col">Driver</th>
                <th scope="col">Reference win chance</th>
                <th scope="col">Comparison win chance</th>
                <th scope="col">Win chance change</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => {
                const a = before?.entries.find((e) => e.entry_key === key);
                const b = after?.entries.find((e) => e.entry_key === key);
                return (
                  <tr key={key}>
                    <th scope="row">
                      {a?.driver_name ?? b?.driver_name ?? 'Driver name unavailable'}
                    </th>
                    <td>{a ? probability(a.win_probability) : 'Entry unavailable'}</td>
                    <td>{b ? probability(b.win_probability) : 'Entry unavailable'}</td>
                    <td>
                      {sameField
                        ? probabilityDelta(a?.win_probability ?? null, b?.win_probability ?? null)
                        : 'Not available'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableRegion>
      )}
    </Panel>
  );
}
export function CorrectionHistory({ data }: { data: EventPerformance }) {
  return (
    <Panel
      title="Results and correction history"
      note={`${horizonName(data.horizon)} · evaluations refer to the original run and exact result revision.`}
    >
      <div className="go-panel-body">
        <p>Run: {data.run_id ?? 'No published forecast'}</p>
        {!data.corrections.length && (
          <p>No result revisions are available. Performance is not available.</p>
        )}
        {data.corrections.map((c) => (
          <section key={c.revision}>
            <h3>
              Result revision {c.revision} · {c.change}
            </h3>
            <p>
              {c.official ? 'Official' : 'Not marked official'} · recorded {c.recorded_at}.
              Provider-specific correction reasons are not publicly verified.
            </p>
            {c.evaluations.length ? (
              c.evaluations.map((e, i) => (
                <div key={i}>
                  <p>
                    Evaluated {e.evaluated_at} · original run {e.run_id}
                  </p>
                  <MetricTable
                    metrics={e.metrics}
                    caption={`Stored evaluation · result revision ${e.result_revision}`}
                  />
                </div>
              ))
            ) : (
              <p>
                No public evaluation for this revision. Earlier scores do not represent this result
                revision.
              </p>
            )}
          </section>
        ))}
      </div>
    </Panel>
  );
}
export function EventResults({ season, eventId }: { season: number; eventId: number }) {
  const [horizon, setHorizon] = useState('pre_weekend');
  const query = useQuery<EventPerformance>(
    `/api/v1/seasons/${season}/events/${eventId}/performance?horizon=${horizon}`,
    'EventPerformance',
  );
  return (
    <>
      <HorizonSelect value={horizon} onChange={setHorizon} />
      <QueryNotice query={query} />
      {query.state === 'ready' && <CorrectionHistory data={query.data} />}
    </>
  );
}
function HorizonSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label className="go-trust-control">
      Evaluation horizon{' '}
      <select
        aria-label="Evaluation horizon"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="pre_weekend">Pre-weekend</option>
        <option value="post_qualifying">After qualifying</option>
      </select>
    </label>
  );
}
export function Performance({ season }: { season: number }) {
  const [horizon, setHorizon] = useState('pre_weekend');
  const [name, setName] = useState('');
  const history = useQuery<HistoricalPerformance>(
    '/api/v1/performance/historical',
    'HistoricalPerformance',
  );
  const live = useQuery<LivePerformance>(
    `/api/v1/seasons/${season}/performance?horizon=${horizon}`,
    'LivePerformance',
  );
  const candidates =
    history.state === 'ready' ? history.data.candidates.filter((c) => c.horizon === horizon) : [];
  const selected = candidates.find((c) => c.name === name) ?? candidates.find((c) => c.retained);
  return (
    <>
      <HorizonSelect value={horizon} onChange={setHorizon} />
      <Panel
        title="Out-of-sample historical reconstruction"
        note="2023–2025 whole-race evaluation; explored archive, not a pristine holdout or verified as-of evidence."
      >
        <div className="go-panel-body">
          <p>
            Weights and calibration use earlier, disjoint race blocks. The archive was explored and
            source/entry availability is unverified. These diagnostics cannot establish prospective
            accuracy or justify promotion. The retained fallback is race-only standings before the
            weekend and qualifying order after qualifying; no challenger was promoted.
          </p>
          <p>
            Summary values use the full 70-race cohort per horizon, independent of the selected
            navigation season. Every variant, poor race, missing forecast and missing metric remains
            inspectable.
          </p>
          <QueryNotice query={history} />
        </div>
        {selected && (
          <>
            <TableRegion label="Historical model and baseline scorecard">
              <table className="go-timing go-trust-table">
                <caption>Stored historical winner scores · identical whole-race cohorts</caption>
                <thead>
                  <tr>
                    <th scope="col">Model / baseline</th>
                    <th scope="col">Winner log loss ↓</th>
                    <th scope="col">Winner pick hit rate</th>
                    <th scope="col">Predicted / scheduled races</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.name}>
                      <th scope="row">
                        {c.name}
                        {c.retained ? ' · retained fallback' : ''}
                      </th>
                      <td>
                        {number(c.metrics.find((m) => m.key === 'winner_log_loss')?.value ?? null)}
                      </td>
                      <td>{metricValue(c.metrics.find((m) => m.key === 'winner_hit')!)}</td>
                      <td>
                        {c.predicted_races}/{c.expected_races}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableRegion>
            <div className="go-panel-body">
              <label>
                Inspect stored model{' '}
                <select
                  aria-label="Inspect stored model"
                  value={selected.name}
                  onChange={(e) => setName(e.target.value)}
                >
                  {candidates.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
              <p>
                Winner log-loss interval: {selected.winner_loss_interval.map(number).join(' to ')} ·
                block bootstrap uses consecutive four-race blocks within seasons. This interval
                describes the historical cohort, not future guarantees.
              </p>
            </div>
            <MetricTable
              metrics={selected.metrics}
              caption={`${selected.name} · stored historical summary`}
            />
            <Panel title="Winner calibration card">
              <div className="go-panel-body">
                <p>
                  Retained baselines use locked identity calibration with tied-rank Plackett–Luce
                  scale 4. Challenger calibrators fit only four earlier held-out races. Small blocks
                  and drift limit calibration claims. Each entrant has weight 1/field size; races
                  have equal weight. Empty bins have unavailable rates. Bin upper bounds are
                  exclusive except the final bin.
                </p>
              </div>
              <TableRegion label="Winner reliability table">
                <table className="go-timing go-trust-table">
                  <caption>
                    {selected.name} · winner reliability · historical reconstruction
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Win chance bin</th>
                      <th scope="col">Mean predicted win chance</th>
                      <th scope="col">Observed winner rate</th>
                      <th scope="col">Entries / races</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.reliability.map((b) => (
                      <tr key={b.lower}>
                        <th scope="row">
                          {probability(b.lower)}–{probability(b.upper)}
                        </th>
                        <td>
                          {b.mean_probability === null
                            ? 'Not available'
                            : probability(b.mean_probability)}
                        </td>
                        <td>
                          {b.observed_rate === null
                            ? 'Not available'
                            : probability(b.observed_rate)}
                        </td>
                        <td>
                          {b.entries}/{b.races}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableRegion>
            </Panel>
            <details className="go-panel-body">
              <summary>All historical race results and exclusions</summary>
              <p>
                True season/round identifiers are retained. Missing rounds are gaps, never
                interpolated; cancelled races are outside the frozen cohort. Missing metric means
                unavailable, not a failed prediction scored as zero.
              </p>
              <TableRegion label="Historical race result comparison">
                <table className="go-timing go-trust-table">
                  <caption>{selected.name} · all scheduled evaluation races</caption>
                  <thead>
                    <tr>
                      <th scope="col">Season / round</th>
                      <th scope="col">Winner log loss</th>
                      <th scope="col">Winner pick hit</th>
                      <th scope="col">Top-three set overlap</th>
                      <th scope="col">Top-ten set overlap</th>
                      <th scope="col">Classified rank MAE</th>
                      <th scope="col">Classified / intended entries</th>
                      <th scope="col">Missing feature cells</th>
                      <th scope="col">Whole-race exclusion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.races.map((r) => (
                      <tr key={`${r.season}/${r.round}`}>
                        <th scope="row">
                          {r.season} / {r.round}
                        </th>
                        <td>{number(r.winner_log_loss)}</td>
                        <td>
                          {r.winner_hit === null ? 'Not available' : probability(r.winner_hit)}
                        </td>
                        <td>
                          {r.top3_overlap === null ? 'Not available' : probability(r.top3_overlap)}
                        </td>
                        <td>
                          {r.top10_overlap === null
                            ? 'Not available'
                            : probability(r.top10_overlap)}
                        </td>
                        <td>{number(r.rank_mae)}</td>
                        <td>
                          {r.classified_entries ?? 'Unknown'}/{r.field_entries ?? 'Unknown'}
                        </td>
                        <td>{r.missing_feature_cells ?? 'Unknown'}</td>
                        <td>
                          {r.missing_reason ?? 'None; non-classified entries excluded from ranking'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableRegion>
            </details>
          </>
        )}
      </Panel>
      <Panel
        title={`Live-issued prospective performance · ${season}`}
        note="Published runs and stored evaluations; separate from reconstructed history."
      >
        <div className="go-panel-body">
          <p>
            No aggregate prospective score has been established. Each event remains visible,
            including missed publications, unevaluated runs and corrections. A published run alone
            does not prove independently verified as-of eligibility or completion of the
            preregistered prospective promotion gate.
          </p>
          <QueryNotice query={live} />
          {live.state === 'ready' &&
            (!live.data.events.length ? (
              <Notice title="No indexed live events">
                <p>Prospective performance is not available.</p>
              </Notice>
            ) : (
              live.data.events.map((e) => (
                <details key={e.event_id}>
                  <summary>
                    Round {e.round} · {e.event_name} · {e.status.split('_').join(' ')}
                  </summary>
                  <CorrectionHistory data={e} />
                </details>
              ))
            ))}
        </div>
      </Panel>
      <Glossary />
    </>
  );
}
export function Glossary() {
  return (
    <Panel title="Metric glossary">
      <dl className="go-panel-body go-glossary">
        <dt>Win probability</dt>
        <dd>
          Chance of being the official race winner, across the original intended entry field.
          Unknown is distinct from a stored zero.
        </dd>
        <dt>Winner pick hit rate</dt>
        <dd>
          Fraction of races in which the first entrant in the stored predicted order is the official
          winner. A tied-probability field can have a deterministic tie-break for this order; it is
          not probability calibration.
        </dd>
        <dt>Exact-position accuracy</dt>
        <dd>
          Fraction of entrants assigned their exact observed rank, under a declared classification
          policy. It is not stored in this benchmark and remains unavailable.
        </dd>
        <dt>Top-three / top-ten set overlap</dt>
        <dd>
          Fraction of eligible observed official top-k finishers present in the predicted top-k set,
          regardless of order. Two correct members of a three-driver podium set means 2/3 set
          overlap, even if neither position is exact. These scores are not individual podium or
          top-ten probabilities.
        </dd>
        <dt>Classified rank MAE and correlation</dt>
        <dd>
          Average absolute rank error and Spearman agreement within classified entrants. Finished,
          lapped and classified retirements are included. DNS, DSQ, unclassified and unknown
          statuses have no ranking label; they stay in the intended winner field. Official
          classification and internal contiguous rank differ.
        </dd>
        <dt>Winner log loss and Brier</dt>
        <dd>
          Proper scores for the official winner; lower is better. Log loss uses natural logarithms,
          with the true winner probability bounded below by 1e-15 only for scoring. Brier sums
          squared errors across the field. Neither is an accuracy percentage.
        </dd>
        <dt>Winner calibration error</dt>
        <dd>
          Weighted difference between mean predicted win chance and observed winner rate in ten
          fixed bins. Lower is better; good calibration on explored history does not guarantee
          future accuracy.
        </dd>
        <dt>Percentage-point change</dt>
        <dd>
          Comparison probability minus reference probability, multiplied by 100. A win chance moving
          from 0.20 to 0.25 increases by +5.0 percentage points, not by five percent relative to the
          earlier value.
        </dd>
        <dt>Not available</dt>
        <dd>
          Missing outcome, denominator, publication or measurement. It must never be interpreted as
          zero probability or perfect performance.
        </dd>
      </dl>
    </Panel>
  );
}
export function Methodology({ sources = false }: { sources?: boolean }) {
  return (
    <>
      <Panel title={sources ? 'Sources, coverage and freshness' : 'Public model card'}>
        <div className="go-panel-body">
          {sources ? (
            <>
              <p>
                Historical research uses Jolpica results and qualifying in the 2022–2025
                reconstruction. Source and entry publication times are unverified; verified as-of
                coverage is zero of 70 races per horizon. Detailed telemetry and weather are not
                established inputs in this evidence.
              </p>
              <p>
                Each published forecast shows its recorded source, input cutoff, actual issue time,
                source-availability timestamp and field coverage. Unknown sources or timing remain
                unavailable; no universal wall-clock staleness threshold is invented. Verified as-of
                cutoff describes the original snapshot, not present-day freshness.
              </p>
              <p>
                Indexed seasons and sessions do not establish complete forecast or result coverage.
                Public provider details are limited to recognized source names; internal logs, paths
                and source manifests stay private.
              </p>
            </>
          ) : (
            <>
              <p>
                The measured selection retained fixed baselines: race-only standings before the
                weekend and verified qualifying order after qualifying. Their Plackett–Luce
                strengths use exp(−mean tied rank / 4), with equal strength for ties. Missing
                standings use the field midpoint; missing qualifying falls back to standings. This
                selection did not create a production champion or publish a live forecast.
              </p>
              <p>
                A published run is identified by its immutable run ID. Its private model manifest is
                not a public model card; a verified model-specific public card is unavailable. Do
                not assume every published run uses the retained research baseline.
              </p>
              <p>
                Only the declared official race-winner probability is shown. Conditional rank/top-k
                simulations assume the fixed field completes and have no retirement, DNS or DSQ
                mechanism. They are withheld; official podium, top-ten, points and retirement
                probabilities are unavailable.
              </p>
            </>
          )}
        </div>
      </Panel>
      <Panel title="Methodology summary">
        <div className="go-panel-body">
          <p>
            Pre-weekend ends before the first competitive session and excludes current qualifying.
            After qualifying requires verified final qualifying/grid readiness and issuance before
            race start. Snapshot timestamps describe recorded availability; per-feature inputs and
            driver-level causal attribution are not public evidence.
          </p>
          <p>
            Historical evaluation uses whole-race forward-time folds for 2023, 2024 and 2025, with
            earlier train/tune/calibration blocks. Configuration and weights never fit on evaluation
            races. Because the archive has been explored and historical availability is unverified,
            this is out-of-sample relative to fitting, with exploratory limitations.
          </p>
          <p>
            Live-issued prospective forecasts, reconstructed historical diagnostics and
            legacy-unverified outputs are separate. Legacy scores never enter this public scorecard.
            Result corrections append a new result revision and evaluation; forecasts are never
            rewritten. No new model has passed the prospective promotion gate.
          </p>
          <p>
            Tables provide the complete accessible numerical evidence; optional win-probability bars
            repeat the table data. Comparisons express associations and uncertainty, without
            invented driver stories or causal claims.
          </p>
        </div>
      </Panel>
      <Glossary />
    </>
  );
}
