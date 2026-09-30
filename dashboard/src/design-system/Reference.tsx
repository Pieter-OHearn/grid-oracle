import { useEffect, useRef, useState } from 'react';
import {
  DataNotice,
  ForecastContext,
  HorizonControl,
  Panel,
  SampleNotice,
  TimingTable,
} from './components';
import { destinations, horizonLabels, sampleEntries } from './sample';
import type { DataState, Horizon, Journey } from './sample';

function readJourney(): Journey {
  const value = window.location.hash.slice(1);
  return destinations.find((item) => item.id === value)?.id ?? 'race';
}
function RaceJourney({
  horizon,
  state,
  navigate,
}: {
  horizon: Horizon;
  state: DataState;
  navigate: (page: Journey) => void;
}) {
  const entries =
    state === 'unknown'
      ? sampleEntries.map((entry, i) => (i === 0 ? { ...entry, pre: null, post: null } : entry))
      : sampleEntries;
  const ready = state === 'ready';
  return (
    <>
      <Panel
        title="Who could win?"
        note={
          ready
            ? 'Leading contenders · 22 synthetic entries'
            : 'Partial field · Known chances and unranked unknown entries'
        }
      >
        <TimingTable entries={entries} horizon={horizon} limit={5} />
        <div className="go-panel-body">
          <a href="#comparison" onClick={() => navigate('comparison')}>
            Compare all 22 entries →
          </a>
        </div>
      </Panel>
      <div className="go-secondary">
        <Panel title={horizon === 'post' ? 'What changed?' : 'The starting picture'}>
          <div className="go-panel-body">
            <p className="go-race-type">
              {ready
                ? horizon === 'post'
                  ? 'Norris · 22% → 28%'
                  : 'Piastri · 25%'
                : 'Movement unknown'}
            </p>
            <p>
              {ready
                ? horizon === 'post'
                  ? '+6 percentage points in this sample, not a 6% relative increase.'
                  : 'This sample uses no information from the upcoming competitive sessions.'
                : 'No comparison is inferred from incomplete data.'}
            </p>
            <a href="#comparison">Compare both horizons</a>
          </div>
        </Panel>
        <Panel title="A favorite, with uncertainty">
          <div className="go-panel-body">
            <p className="go-race-type">
              {ready
                ? `${horizon === 'post' ? 72 : 75}% chance someone else wins`
                : 'Uncertainty unknown'}
            </p>
            <p>
              A favorite can still be more likely to lose than win. These illustrative probabilities
              do not guarantee an outcome.
            </p>
            <a href="#methodology">How to read probabilities</a>
          </div>
        </Panel>
      </div>
    </>
  );
}
function ScorecardJourney({ horizon }: { horizon: Horizon }) {
  const [provenance, setProvenance] = useState('live');
  return (
    <>
      <Panel
        title="Public scorecard"
        note={`${horizonLabels[horizon]} · Sample layout, no measured performance`}
      >
        <div className="go-panel-body">
          <label>
            Provenance{' '}
            <select value={provenance} onChange={(event) => setProvenance(event.target.value)}>
              <option value="live">Live-issued</option>
              <option>Historical reconstruction</option>
              <option>Legacy unverified</option>
            </select>
          </label>
          <p className="go-filter-note" role="status">
            {provenance === 'live'
              ? 'Live-issued cohort: no published sample runs.'
              : provenance === 'Historical reconstruction'
                ? 'Historical reconstruction cohort: hindsight reconstruction is separate from live-issued evidence.'
                : 'Legacy unverified cohort: excluded from validated performance claims.'}
          </p>
          <div className="go-metrics">
            <div>
              <strong>Not measured</strong>
              <span>Winner log loss · lower is better</span>
            </div>
            <div>
              <strong>0 evaluated</strong>
              <span>0 eligible races · sample cohort</span>
            </div>
            <div>
              <strong>Unknown</strong>
              <span>Calibration / uncertainty interval</span>
            </div>
          </div>
          <p>
            Performance belongs to a named horizon, cohort and version. Missed issuances stay in
            coverage; small samples do not prove accuracy. Legacy unverified outputs are not
            eligible evidence.
          </p>
          <a href="#archive">Inspect individual forecast snapshots →</a>
        </div>
      </Panel>
      <Panel title="Coverage and limitations">
        <div className="go-panel-body">
          <p>
            No benchmark results are connected to this design reference. Baseline comparison,
            evaluation dates and calibration diagrams require WP12’s verified artifacts.
          </p>
          <a href="#methodology">Scoring methodology</a>
        </div>
      </Panel>
    </>
  );
}
function ArchiveJourney({ navigate }: { navigate: (page: Journey) => void }) {
  const [season, setSeason] = useState('2026');
  return (
    <Panel title="Season archive" note="Illustrative destinations; no historical claim">
      <div className="go-panel-body">
        <label>
          Example season{' '}
          <select value={season} onChange={(event) => setSeason(event.target.value)}>
            <option>2026</option>
            <option>2025</option>
            <option>2018</option>
          </select>
        </label>
        <p className="go-filter-note" role="status">
          {season} example archive · Synthetic coverage only
        </p>
        <ul className="go-archive">
          <li>
            <strong>British Grand Prix · July 2026 sample</strong>
            <p>Two horizon snapshots · Synthetic, not live-issued</p>
            <a href="#race" onClick={() => navigate('race')}>
              Open sample race →
            </a>
            <a href="#comparison">Compare snapshots</a>
          </li>
          <li>
            <strong>Example cancelled event</strong>
            <p>Cancelled · No forecast expected</p>
          </li>
          <li>
            <strong>Example results-only event</strong>
            <p>Forecast unavailable · Historical results do not establish an as-of forecast</p>
          </li>
        </ul>
        <p>
          The selector changes the example archive label only. Opening the race always opens the
          explicitly labelled July 2026 sample. Real season URLs, entries and archive depth belong
          to WP11.
        </p>
      </div>
    </Panel>
  );
}
function InformationJourney({ page }: { page: Journey }) {
  return (
    <Panel title={page === 'sources' ? 'Data sources' : 'How to read the forecast'}>
      <div className="go-panel-body">
        {page === 'sources' ? (
          <>
            <p>
              All values here are synthetic. No provider, API, model or real forecast is connected.
            </p>
            <p>
              Production source attribution, rights and per-source freshness will use the WP04/WP11
              contracts. Unknown timestamps must be shown as unknown.
            </p>
          </>
        ) : (
          <>
            <p>
              Win probabilities describe mutually exclusive winners and sum to 100% across a
              complete field. A 28% chance means roughly 28 wins per 100 comparable events if
              calibrated; it does not promise this race’s outcome.
            </p>
            <p>
              Pre-weekend uses data before the first competitive session. After qualifying requires
              verified final qualifying/grid data and a cutoff before race start. Compare immutable
              snapshots; revisions never erase earlier runs.
            </p>
            <p>
              Changes use percentage points: 22% to 28% is +6 pp. Uncertainty includes model
              calibration, data coverage and sample size; a probability is not a score-gap
              confidence measure.
            </p>
          </>
        )}
        <a href="#race">Back to race weekend</a>
      </div>
    </Panel>
  );
}
function JourneyContent({
  page,
  horizon,
  state,
  navigate,
}: {
  page: Journey;
  horizon: Horizon;
  state: DataState;
  navigate: (page: Journey) => void;
}) {
  if (page === 'race') return <RaceJourney horizon={horizon} state={state} navigate={navigate} />;
  if (page === 'comparison')
    return (
      <Panel
        title="Full-field comparison"
        note="All 22 sample entries · Sorted by selected horizon"
      >
        <TimingTable
          entries={
            state === 'unknown'
              ? sampleEntries.map((entry, i) => (i === 0 ? { ...entry, post: null } : entry))
              : sampleEntries
          }
          horizon={horizon}
          comparison
        />
        <div className="go-panel-body">
          <a href="#race">Back to leading contenders</a>
        </div>
      </Panel>
    );
  if (page === 'scorecard') return <ScorecardJourney horizon={horizon} />;
  if (page === 'archive') return <ArchiveJourney navigate={navigate} />;
  return <InformationJourney page={page} />;
}
export function DesignReference() {
  const [page, setPage] = useState<Journey>(readJourney);
  const [horizon, setHorizon] = useState<Horizon>('post');
  const [state, setState] = useState<DataState>('ready');
  const [appearance, setAppearance] = useState('system');
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const update = () => {
      if (window.location.hash === '#content') return;
      setPage(readJourney());
      setState('ready');
      heading.current?.focus();
    };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const navigate = (destination: Journey) => {
    window.location.hash = destination;
  };
  const label = destinations.find((item) => item.id === page)?.label ?? 'Race weekend';
  const showContent = state === 'ready' || state === 'unknown';
  return (
    <div className="go-system" data-appearance={appearance}>
      <a className="go-skip" href="#content">
        Skip to content
      </a>
      <div className="go-shell">
        <aside className="go-sidebar">
          <div className="go-brand">
            <span className="go-mark" aria-hidden="true" />
            GRIDORACLE
          </div>
          <nav aria-label="Main navigation">
            {destinations.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                aria-current={page === item.id ? 'page' : undefined}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <p className="go-muted go-sidebar-foot">
            Independent F1 forecasts
            <br />
            WP10 design reference
          </p>
        </aside>
        <div className="go-main">
          <header className="go-topbar">
            <span>Formula 1 / {label}</span>
            <SampleNotice />
          </header>
          <main id="content" tabIndex={-1}>
            <div className="go-heading">
              <p className="go-eyebrow">
                {page === 'race' || page === 'comparison'
                  ? 'GBR / Silverstone · Synthetic context'
                  : 'GridOracle / Design reference'}
              </p>
              <h1 ref={heading} tabIndex={-1}>
                {page === 'race' ? 'British Grand Prix' : label}
              </h1>
              <p className="go-muted">
                {page === 'race'
                  ? 'The race ahead, in probabilities.'
                  : 'Transparent forecasts, preserved on record.'}
              </p>
            </div>
            <div className="go-toolbar">
              <HorizonControl value={horizon} onChange={setHorizon} />
              <label>
                Appearance{' '}
                <select value={appearance} onChange={(event) => setAppearance(event.target.value)}>
                  <option value="system">Follow device</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </label>
            </div>
            <ForecastContext horizon={horizon} unknown={state === 'unknown'} />
            <details className="go-preview-controls">
              <summary>Explore component states · sample controls</summary>
              <label>
                Data state{' '}
                <select
                  value={state}
                  onChange={(event) => setState(event.target.value as DataState)}
                >
                  {['ready', 'loading', 'unavailable', 'error', 'unknown', 'empty'].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <p>These controls simulate states on every journey; retry restores sample data.</p>
            </details>
            <div aria-busy={state === 'loading'}>
              <DataNotice
                journey={page}
                state={state}
                onRetry={() => {
                  setState('ready');
                  heading.current?.focus();
                }}
              />
              {showContent && (
                <JourneyContent page={page} horizon={horizon} state={state} navigate={navigate} />
              )}
            </div>
            <footer>
              <SampleNotice />
              <p className="go-muted">
                Sample July 2026 context · No API calls · No production forecasts
              </p>
            </footer>
          </main>
        </div>
      </div>
    </div>
  );
}
