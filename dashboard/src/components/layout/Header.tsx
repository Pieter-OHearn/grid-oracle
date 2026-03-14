import { ChevronLeft, ChevronRight, Menu, X } from 'lucide-react';
import { useParams, useLocation } from 'react-router';
import { HeaderBreadcrumb } from './HeaderBreadcrumb';
import { HeaderTabs } from './HeaderTabs';
import { RACES } from '../../data';

interface Props {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onRaceSelect: (id: string) => void;
}

export function Header({ sidebarOpen, onToggleSidebar, onRaceSelect }: Props) {
  const { raceId } = useParams();
  const location = useLocation();
  const isDashboard = location.pathname === '/dashboard';
  const selectedRace = RACES.find((r) => r.id === raceId);
  const selectedIdx = selectedRace ? RACES.findIndex((r) => r.id === selectedRace.id) : -1;

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
            onClick={() => selectedIdx > 0 && onRaceSelect(RACES[selectedIdx - 1].id)}
            disabled={selectedIdx <= 0}
            className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() =>
              selectedIdx < RACES.length - 1 && onRaceSelect(RACES[selectedIdx + 1].id)
            }
            disabled={selectedIdx >= RACES.length - 1}
            className="p-1.5 rounded hover:bg-[#1e1e30] text-[#6b7280] hover:text-white disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </header>
  );
}
