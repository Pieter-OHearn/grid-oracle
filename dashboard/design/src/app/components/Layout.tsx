import { useState } from 'react';
import { Outlet, NavLink, useNavigate, useParams, useLocation } from 'react-router';
import { motion, AnimatePresence } from 'motion/react';
import { BarChart2, ChevronLeft, ChevronRight, Activity, Menu, X, Flag, Clock, CheckCircle } from 'lucide-react';
import { RACES } from '../data/mockData';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const navigate = useNavigate();
  const { raceId } = useParams();
  const location = useLocation();

  const selectedRace = RACES.find(r => r.id === raceId);
  const isDashboard = location.pathname === '/dashboard';

  const handleRaceSelect = (id: string) => {
    const race = RACES.find(r => r.id === id);
    if (!race) return;
    const isResultsPage = location.pathname.includes('/results');
    if (isResultsPage && (race.status === 'completed')) {
      navigate(`/race/${id}/results`);
    } else {
      navigate(`/race/${id}`);
    }
  };

  return (
    <div className="flex h-screen bg-[#08080e] text-white overflow-hidden" style={{ fontFamily: "'Barlow', sans-serif" }}>
      {/* Sidebar */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="flex-shrink-0 h-full bg-[#0c0c16] border-r border-[#1e1e30] flex flex-col overflow-hidden"
          >
            {/* Logo */}
            <div className="px-5 py-4 border-b border-[#1e1e30] flex items-center gap-3 flex-shrink-0">
              <div className="w-7 h-7 rounded flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #e10600, #ff4444)' }}>
                <Activity size={14} className="text-white" />
              </div>
              <span className="text-white tracking-widest uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1rem', fontWeight: 700, letterSpacing: '0.12em' }}>
                Grid<span style={{ color: '#e10600' }}>Oracle</span>
              </span>
            </div>

            {/* Nav Links */}
            <div className="px-3 py-3 flex-shrink-0 border-b border-[#1e1e30]">
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded text-xs uppercase tracking-wider transition-all duration-200 ${
                    isActive
                      ? 'bg-[#e10600]/15 text-[#e10600] border border-[#e10600]/30'
                      : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
                  }`
                }
                style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.08em' }}
              >
                <BarChart2 size={14} />
                Season Dashboard
              </NavLink>
            </div>

            {/* Race List */}
            <div className="flex-1 overflow-y-auto py-2 scrollbar-thin">
              <div className="px-4 py-2 mb-1">
                <span className="text-[10px] uppercase tracking-widest text-[#3a3a52]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                  2025 Calendar
                </span>
              </div>
              {RACES.map(race => {
                const isSelected = race.id === raceId;
                return (
                  <button
                    key={race.id}
                    onClick={() => handleRaceSelect(race.id)}
                    className={`w-full text-left px-4 py-2.5 transition-all duration-150 flex items-center gap-3 group ${
                      isSelected
                        ? 'bg-[#1a1a28] border-r-2 border-[#e10600]'
                        : 'hover:bg-[#131320]'
                    }`}
                  >
                    {/* Round number */}
                    <span
                      className="text-[10px] text-[#3a3a52] flex-shrink-0 w-5 text-right"
                      style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}
                    >
                      {String(race.round).padStart(2, '0')}
                    </span>
                    {/* Flag */}
                    <span className="text-base flex-shrink-0">{race.countryFlag}</span>
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div
                        className={`text-xs truncate ${isSelected ? 'text-white' : 'text-[#9090a8] group-hover:text-white'}`}
                        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.03em' }}
                      >
                        {race.shortName} · {race.country}
                      </div>
                    </div>
                    {/* Status */}
                    {race.status === 'completed' && (
                      <CheckCircle size={11} className="flex-shrink-0 text-[#22c55e] opacity-70" />
                    )}
                    {race.status === 'next' && (
                      <div className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-[#e10600] animate-pulse" />
                    )}
                    {race.status === 'upcoming' && (
                      <Clock size={11} className="flex-shrink-0 text-[#3a3a52]" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[#1e1e30] flex-shrink-0">
              <p className="text-[10px] text-[#2e2e45]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                MODEL v2.4.1 · 2025 SEASON
              </p>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top header */}
        <header className="flex-shrink-0 h-14 bg-[#0a0a14] border-b border-[#1e1e30] flex items-center px-4 gap-4">
          <button
            onClick={() => setSidebarOpen(v => !v)}
            className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white transition-colors"
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>

          {/* Breadcrumb */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {isDashboard ? (
              <div className="flex items-center gap-2">
                <BarChart2 size={14} className="text-[#e10600]" />
                <span className="text-white text-sm" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.05em' }}>
                  Season Dashboard
                </span>
              </div>
            ) : selectedRace ? (
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-lg flex-shrink-0">{selectedRace.countryFlag}</span>
                <div className="min-w-0">
                  <span className="text-white text-sm truncate" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.05em' }}>
                    {selectedRace.name}
                  </span>
                  <span className="text-[#3a3a52] text-xs ml-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    · {selectedRace.circuit}
                  </span>
                </div>
              </div>
            ) : null}
          </div>

          {/* Race page tabs */}
          {!isDashboard && selectedRace && (
            <div className="flex items-center gap-1">
              <NavLink
                to={`/race/${selectedRace.id}`}
                end
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-xs transition-all duration-150 ${
                    isActive
                      ? 'bg-[#e10600] text-white'
                      : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
                  }`
                }
                style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}
              >
                Prediction
              </NavLink>
              {selectedRace.status === 'completed' && (
                <NavLink
                  to={`/race/${selectedRace.id}/results`}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded text-xs transition-all duration-150 ${
                      isActive
                        ? 'bg-[#e10600] text-white'
                        : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
                    }`
                  }
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}
                >
                  Results
                </NavLink>
              )}
            </div>
          )}

          {/* Prev / Next race */}
          {!isDashboard && selectedRace && (
            <div className="flex items-center gap-1 ml-auto">
              <button
                onClick={() => {
                  const idx = RACES.findIndex(r => r.id === selectedRace.id);
                  if (idx > 0) handleRaceSelect(RACES[idx - 1].id);
                }}
                disabled={RACES.findIndex(r => r.id === selectedRace.id) === 0}
                className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => {
                  const idx = RACES.findIndex(r => r.id === selectedRace.id);
                  if (idx < RACES.length - 1) handleRaceSelect(RACES[idx + 1].id);
                }}
                disabled={RACES.findIndex(r => r.id === selectedRace.id) === RACES.length - 1}
                className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
