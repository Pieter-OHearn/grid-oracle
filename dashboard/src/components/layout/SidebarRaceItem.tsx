import { CheckCircle, Clock } from 'lucide-react';
import type { Race } from '../../types';

interface Props {
  race: Race;
  isSelected: boolean;
  onClick: () => void;
}

export function SidebarRaceItem({ race, isSelected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-2.5 transition-all duration-150 flex items-center gap-3 group ${
        isSelected ? 'bg-[#1a1a28] border-r-2 border-[#e10600]' : 'hover:bg-[#131320]'
      }`}
    >
      <span
        className="text-[10px] text-[#3a3a52] flex-shrink-0 w-5 text-right"
        style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}
      >
        {String(race.round).padStart(2, '0')}
      </span>

      <span className="text-base flex-shrink-0">{race.countryFlag}</span>

      <div className="flex-1 min-w-0">
        <div
          className={`text-xs truncate ${isSelected ? 'text-white' : 'text-[#9090a8] group-hover:text-white'}`}
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 600,
            letterSpacing: '0.03em',
          }}
        >
          {race.shortName} · {race.country}
        </div>
      </div>

      {race.status === 'completed' && (
        <CheckCircle size={11} className="flex-shrink-0 text-[#22c55e] opacity-70" />
      )}
      {race.status === 'next' && (
        <div className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-[#e10600] animate-pulse" />
      )}
      {race.status === 'upcoming' && <Clock size={11} className="flex-shrink-0 text-[#3a3a52]" />}
    </button>
  );
}
