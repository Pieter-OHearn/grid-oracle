import { ChevronLeft, ChevronRight, Menu, X } from 'lucide-react';
import { useParams, useLocation, useNavigate } from 'react-router';
import { HeaderBreadcrumb } from './HeaderBreadcrumb';
import { HeaderTabs } from './HeaderTabs';
import { useRaceList } from '../../context/RaceListContext';

interface Props {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function Header({ sidebarOpen, onToggleSidebar }: Props) {
  const { raceId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { races } = useRaceList();
  const isDashboard = location.pathname === '/dashboard';

  const numericId = raceId != null ? Number(raceId) : undefined;
  const selectedIdx = numericId != null ? races.findIndex((r) => r.id === numericId) : -1;
  const selectedRace = selectedIdx >= 0 ? races[selectedIdx] : undefined;

  const goToRace = (idx: number) => {
    const race = races[idx];
    if (!race) return;
    const isResultsPage = location.pathname.includes('/results');
    if (isResultsPage && race.is_completed) {
      navigate(`/race/${race.id}/results`);
    } else {
      navigate(`/race/${race.id}`);
    }
  };

  return (
    <header className="flex-shrink-0 h-14 bg-[#0a0a14] border-b border-[#1e1e30] flex items-center px-4 gap-4">
      <button
        onClick={onToggleSidebar}
        className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white transition-colors"
      >
        {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
      </button>

      <div className="flex items-center gap-2 flex-1 min-w-0">
        <HeaderBreadcrumb isDashboard={isDashboard} selectedRace={selectedRace} />
      </div>

      {!isDashboard && selectedRace && <HeaderTabs race={selectedRace} />}

      {!isDashboard && selectedRace && (
        <div className="flex items-center gap-1 ml-auto">
          <button
            onClick={() => goToRace(selectedIdx - 1)}
            disabled={selectedIdx <= 0}
            className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => goToRace(selectedIdx + 1)}
            disabled={selectedIdx >= races.length - 1}
            className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </header>
  );
}
