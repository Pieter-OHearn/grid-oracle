import { NavLink, useNavigate, useParams, useLocation } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { Logo } from './Logo';
import { SidebarRaceItem } from './SidebarRaceItem';
import { RACES } from '../../data';

interface Props {
  open: boolean;
}

export function Sidebar({ open }: Props) {
  const navigate = useNavigate();
  const { raceId } = useParams();
  const location = useLocation();

  const handleRaceSelect = (id: string) => {
    const race = RACES.find((r) => r.id === id);
    if (!race) return;
    const isResultsPage = location.pathname.includes('/results');
    if (isResultsPage && race.status === 'completed') {
      navigate(`/race/${id}/results`);
    } else {
      navigate(`/race/${id}`);
    }
  };

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 260, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeInOut' }}
          className="flex-shrink-0 h-full bg-[#0c0c16] border-r border-[#1e1e30] flex flex-col overflow-hidden"
        >
          <Logo />

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
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontWeight: 600,
                letterSpacing: '0.08em',
              }}
            >
              <BarChart2 size={14} />
              Season Dashboard
            </NavLink>
          </div>

          <div className="flex-1 overflow-y-auto py-2 scrollbar-thin">
            <div className="px-4 py-2 mb-1">
              <span
                className="text-[10px] uppercase tracking-widest text-[#3a3a52]"
                style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
              >
                2025 Calendar
              </span>
            </div>
            {RACES.map((race) => (
              <SidebarRaceItem
                key={race.id}
                race={race}
                isSelected={race.id === raceId}
                onClick={() => handleRaceSelect(race.id)}
              />
            ))}
          </div>

          <div className="px-5 py-3 border-t border-[#1e1e30] flex-shrink-0">
            <p className="text-[10px] text-[#2e2e45]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              MODEL v2.4.1 · 2025 SEASON
            </p>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
