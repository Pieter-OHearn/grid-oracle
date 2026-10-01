import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router';
import type { Event, EventIndex, ForecastSelection, SeasonIndex, SessionIndex } from './contract';
import { useQuery } from './query';
import { eventPath, seasonPath, switchSeasonPath } from './navigation';
import { FieldTable, ForecastContext, Notice, QueryNotice } from './components';
import { Panel } from '../design-system/Panel';
import { DriverDetail, RunComparison, EventResults, Performance, Methodology } from './Trust';
import '../design-system/tokens.css';
import './app.css';

const Distribution = lazy(() => import('./Distribution'));
const api = '/api/v1';

function FocusHeading() {
  const location = useLocation();
  useEffect(() => {
    document.querySelector<HTMLElement>('h1')?.focus();
  }, [location.pathname]);
  return null;
}
function Heading({ title, note }: { title: string; note?: string }) {
  const { season } = useParams();
  return (
    <header className="go-heading">
      <p className="go-eyebrow">Season {season ?? 'index'} · GridOracle</p>
      <h1 tabIndex={-1}>{title}</h1>
      {note && <p className="go-muted">{note}</p>}
    </header>
  );
}
function Shell() {
  const { season } = useParams();
  const year = Number(season);
  const location = useLocation();
  const navigate = useNavigate();
  const seasons = useQuery<SeasonIndex>(`${api}/seasons`, 'SeasonIndex');
  const main = useRef<HTMLElement>(null);
  const destinations = [
    ['weekend', 'Race weekend'],
    ['events', 'Seasons / archive'],
    ['record', 'Track record'],
    ['methodology', 'Methodology'],
    ['sources', 'Sources'],
  ];
  return (
    <div className="go-system go-public">
      <div className="go-shell">
        <a
          className="go-skip"
          href="#main"
          onClick={(event) => {
            event.preventDefault();
            main.current?.focus();
          }}
        >
          Skip to main content
        </a>
        <aside className="go-sidebar">
          <div className="go-brand">
            <span className="go-mark" aria-hidden="true" />
            GridOracle
          </div>
          <nav aria-label="Main navigation">
            {destinations.map(([path, label]) => (
              <Link
                key={path}
                to={seasonPath(year, path)}
                aria-current={
                  (location.pathname.split('/')[3] === path &&
                    !(path === 'events' && location.pathname.split('/')[4])) ||
                  (path === 'weekend' && !!location.pathname.split('/')[4])
                    ? 'page'
                    : undefined
                }
              >
                {label}
              </Link>
            ))}
          </nav>
          <p className="go-sidebar-foot go-muted">
            Immutable forecasts.
            <br />
            Season-specific context.
          </p>
        </aside>
        <div className="go-main">
          <header className="go-topbar">
            <span>GridOracle / {season}</span>
            <label>
              Season{' '}
              <select
                aria-label="Season"
                value={season}
                onChange={(event) =>
                  navigate(
                    switchSeasonPath(
                      location.pathname,
                      Number(event.target.value),
                      location.search,
                    ),
                  )
                }
              >
                {seasons.state === 'ready' &&
                seasons.data.seasons.some((s) => s.year === year) ? null : (
                  <option value={season}>{season}</option>
                )}
                {seasons.state === 'ready' &&
                  seasons.data.seasons.map((s) => (
                    <option key={s.year} value={s.year}>
                      {s.year}
                    </option>
                  ))}
              </select>
            </label>
          </header>
          <main id="main" tabIndex={-1} ref={main}>
            <FocusHeading />
            {seasons.state === 'error' && <QueryNotice query={seasons} />}
            <Outlet key={season} />
            <footer className="go-muted">
              <p>
                Published probabilities are snapshots at a specific cutoff. Missing data stays
                unknown.
              </p>
            </footer>
          </main>
        </div>
      </div>
    </div>
  );
}
function Start() {
  const query = useQuery<SeasonIndex>(`${api}/seasons`, 'SeasonIndex');
  if (query.state !== 'ready') return <StandaloneNotice query={query} />;
  if (!query.data.seasons.length)
    return (
      <div className="go-system">
        <Heading title="No supported seasons" />
        <Notice title="Season index is empty">
          <p>No season has been indexed yet.</p>
        </Notice>
      </div>
    );
  return <Navigate to={seasonPath(query.data.seasons[0].year)} replace />;
}
function StandaloneNotice({ query }: { query: Parameters<typeof QueryNotice>[0]['query'] }) {
  return (
    <div className="go-system">
      <Heading title="GridOracle" />
      <QueryNotice query={query} />
    </div>
  );
}
function LegacyRace() {
  const { raceId } = useParams();
  const location = useLocation();
  const query = useQuery<Event>(`${api}/legacy/races/${encodeURIComponent(raceId ?? '')}`, 'Event');
  if (query.state !== 'ready') return <StandaloneNotice query={query} />;
  return (
    <Navigate
      to={eventPath(
        query.data.season,
        query.data.id,
        location.pathname.endsWith('/results') ? 'results' : '',
      )}
      replace
    />
  );
}
function SeasonEvents({ history = false }: { history?: boolean }) {
  const { season } = useParams();
  const query = useQuery<EventIndex>(`${api}/seasons/${season}/events`, 'EventIndex');
  return (
    <>
      <Heading
        title={history ? 'Publication history' : `${season} season archive`}
        note={
          history
            ? 'Published horizon coverage. Public performance evaluation follows separately.'
            : 'Choose an event to inspect its original forecast snapshots.'
        }
      />
      <div aria-busy={query.state === 'loading'}>
        <QueryNotice query={query} />
        {query.state === 'ready' && <EventList events={query.data.events} />}
      </div>
    </>
  );
}
function EventList({ events }: { events: Event[] }) {
  if (!events.length)
    return (
      <Notice title="No indexed events">
        <p>This season has an empty event index. Historical coverage cannot be inferred.</p>
      </Notice>
    );
  return (
    <Panel title="Event index">
      <div className="go-panel-body">
        <ul className="go-archive">
          {events.map((event) => (
            <li key={event.id}>
              <p className="go-eyebrow">
                Round {String(event.round).padStart(2, '0')} · {event.date}
              </p>
              <Link to={eventPath(event.season, event.id)} className="go-race-type">
                {event.name}
              </Link>
              <div className="go-event-meta go-muted">
                <span>{event.lifecycle}</span>
                <span>{event.circuit_name ?? 'Historical circuit name unavailable'}</span>
                <span>
                  {event.coverage.available ?? 'Unknown'}/{event.coverage.expected ?? 'Unknown'}{' '}
                  horizons published
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
function Weekend() {
  const { season } = useParams();
  const [search] = useSearchParams();
  const query = useQuery<EventIndex>(`${api}/seasons/${season}/events`, 'EventIndex');
  if (query.state !== 'ready')
    return (
      <>
        <Heading title="Race weekend" />
        <QueryNotice query={query} />
      </>
    );
  const events = query.data.events.filter((event) => event.lifecycle !== 'cancelled');
  const today = new Date().toISOString().slice(0, 10);
  const selected = events.find((event) => event.date >= today) ?? events[events.length - 1];
  if (!selected)
    return (
      <>
        <Heading title="Race weekend" />
        <EventList events={query.data.events} />
      </>
    );
  const view = search.get('view');
  return (
    <Navigate
      to={`${eventPath(Number(season), selected.id, view === 'field' || view === 'sessions' ? view : '')}?${search}`}
      replace
    />
  );
}
function ForecastBody({
  season,
  eventId,
  full,
}: {
  season: number;
  eventId: number;
  full: boolean;
}) {
  const [search, setSearch] = useSearchParams();
  const horizon = search.get('horizon') === 'post_qualifying' ? 'post_qualifying' : 'pre_weekend';
  const [chart, setChart] = useState(false);
  const query = useQuery<ForecastSelection>(
    `${api}/seasons/${season}/events/${eventId}/forecast?horizon=${horizon}`,
    'ForecastSelection',
  );
  const hadError = useRef(false);
  useEffect(() => {
    if (query.state === 'error') hadError.current = true;
    if (query.state === 'ready' && hadError.current) {
      document.querySelector<HTMLElement>('h1')?.focus();
      hadError.current = false;
    }
  }, [query.state]);
  return (
    <>
      <div className="go-toolbar">
        <div className="go-horizons" role="group" aria-label="Forecast horizon">
          {(['pre_weekend', 'post_qualifying'] as const).map((value, index) => (
            <button
              key={value}
              aria-pressed={horizon === value}
              onClick={() => {
                const next = new URLSearchParams(search);
                next.set('horizon', value);
                setSearch(next);
              }}
            >
              <span className="go-number">0{index + 1}</span>{' '}
              {value === 'pre_weekend' ? 'Pre-weekend' : 'After qualifying'}
            </button>
          ))}
        </div>
        <Link to={`${eventPath(season, eventId, full ? '' : 'field')}?${search}`}>
          {full ? 'Back to race weekend' : 'Compare full field'}
        </Link>
      </div>
      <div aria-busy={query.state === 'loading'}>
        <QueryNotice query={query} />
        {query.state === 'ready' &&
          (query.data.state === 'unavailable' || !query.data.run ? (
            <Notice title="No published forecast">
              <p>
                No approved run has been published for this horizon. This is distinct from an API
                failure.
              </p>
            </Notice>
          ) : (
            <>
              <ForecastContext run={query.data.run} />
              <FieldTable run={query.data.run} limit={full ? undefined : 5} />
              <DriverDetail key={query.data.run.run_id} run={query.data.run} />
              {full && (
                <>
                  <button aria-expanded={chart} onClick={() => setChart(!chart)}>
                    {chart ? 'Hide' : 'Show'} probability chart
                  </button>
                  {chart && (
                    <Suspense
                      fallback={
                        <Notice title="Loading visualization">
                          <p>The published table remains available.</p>
                        </Notice>
                      }
                    >
                      <Distribution entries={query.data.run.entries} />
                    </Suspense>
                  )}
                </>
              )}
            </>
          ))}
      </div>
      <RunComparison season={season} eventId={eventId} />
    </>
  );
}
function EventPage({
  full = false,
  sessionView = false,
  resultsView = false,
}: {
  full?: boolean;
  sessionView?: boolean;
  resultsView?: boolean;
}) {
  const { season, eventId } = useParams();
  const query = useQuery<Event>(`${api}/seasons/${season}/events/${eventId}`, 'Event');
  return (
    <>
      <Heading
        title={query.state === 'ready' ? query.data.name : 'Event'}
        note={
          query.state === 'ready'
            ? `${query.data.date} · ${query.data.lifecycle} · ${query.data.circuit_name ?? 'Historical circuit name unavailable'}`
            : undefined
        }
      />
      <QueryNotice query={query} />
      {query.state === 'ready' && (
        <>
          <p>
            <Link to={seasonPath(Number(season), 'events')}>Season archive</Link> ·{' '}
            <Link to={eventPath(Number(season), query.data.id, sessionView ? '' : 'sessions')}>
              {sessionView ? 'Forecasts' : 'Session schedule'}
            </Link>{' '}
            ·{' '}
            <Link to={eventPath(Number(season), query.data.id, resultsView ? '' : 'results')}>
              {resultsView ? 'Forecasts' : 'Results and corrections'}
            </Link>
          </p>
          {resultsView ? (
            <EventResults season={Number(season)} eventId={query.data.id} />
          ) : sessionView ? (
            <Sessions season={Number(season)} eventId={query.data.id} />
          ) : (
            <ForecastBody
              key={`${season}/${eventId}`}
              season={Number(season)}
              eventId={query.data.id}
              full={full}
            />
          )}
        </>
      )}
    </>
  );
}
function Sessions({ season, eventId }: { season: number; eventId: number }) {
  const query = useQuery<SessionIndex>(
    `${api}/seasons/${season}/events/${eventId}/sessions`,
    'SessionIndex',
  );
  return (
    <>
      <QueryNotice query={query} />
      {query.state === 'ready' &&
        (query.data.sessions.length ? (
          <Panel
            title="Session schedule"
            note="Latest recorded revision for each session; all times UTC."
          >
            <div className="go-panel-body">
              <ul className="go-session-list">
                {query.data.sessions.map((session) => (
                  <li key={session.id}>
                    <strong>{session.kind.split('_').join(' ')}</strong>
                    <br />
                    {new Date(session.scheduled_at).toLocaleString(undefined, {
                      timeZone: 'UTC',
                    })}{' '}
                    UTC · {session.status} · revision {session.revision}
                  </li>
                ))}
              </ul>
            </div>
          </Panel>
        ) : (
          <Notice title="Session schedule unavailable">
            <p>No session times are indexed for this event.</p>
          </Notice>
        ))}
    </>
  );
}
function Policy({ sources = false }: { sources?: boolean }) {
  return (
    <>
      <Heading title={sources ? 'Sources' : 'Methodology'} />
      <Methodology sources={sources} />
    </>
  );
}
function Record() {
  const { season } = useParams();
  return (
    <>
      <Heading
        title="Track record"
        note="Stored historical diagnostics and live-issued prospective evidence, with separate information boundaries."
      />
      <Performance season={Number(season)} />
    </>
  );
}
function NotFound() {
  return (
    <>
      <Heading title="Page not found" />
      <Notice title="Unknown season URL">
        <p>Use the season archive to select an indexed event.</p>
      </Notice>
    </>
  );
}
export default function PublicApp() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Start />} />
        <Route path="/dashboard" element={<Start />} />
        <Route path="/race/:raceId" element={<LegacyRace />} />
        <Route path="/race/:raceId/results" element={<LegacyRace />} />
        <Route path="/seasons/:season" element={<Shell />}>
          <Route index element={<Navigate to="weekend" replace />} />
          <Route path="weekend" element={<Weekend />} />
          <Route path="events" element={<SeasonEvents />} />
          <Route path="events/:eventId" element={<EventPage />} />
          <Route path="events/:eventId/field" element={<EventPage full />} />
          <Route path="events/:eventId/sessions" element={<EventPage sessionView />} />
          <Route path="events/:eventId/results" element={<EventPage resultsView />} />
          <Route path="record" element={<Record />} />
          <Route path="methodology" element={<Policy />} />
          <Route path="sources" element={<Policy sources />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route
          path="*"
          element={
            <div className="go-system">
              <Heading title="Page not found" />
              <Link to="/">Open season index</Link>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
