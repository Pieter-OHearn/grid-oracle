import { BarChart2 } from 'lucide-react';
import type { Race } from '../../types';

interface Props {
  isDashboard: boolean;
  selectedRace?: Race;
}

export function HeaderBreadcrumb({ isDashboard, selectedRace }: Props) {
  if (isDashboard) {
    return (
      <div className="flex items-center gap-2">
        <BarChart2 size={14} className="text-[#e10600]" />
        <span
          className="text-white text-sm"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 600,
            letterSpacing: '0.05em',
          }}
        >
          Season Dashboard
        </span>
      </div>
    );
  }

  if (selectedRace) {
    return (
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-lg flex-shrink-0">{selectedRace.countryFlag}</span>
        <div className="min-w-0">
          <span
            className="text-white text-sm truncate"
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontWeight: 600,
              letterSpacing: '0.05em',
            }}
          >
            {selectedRace.name}
          </span>
          <span
            className="text-[#3a3a52] text-xs ml-2"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            · {selectedRace.circuit}
          </span>
        </div>
      </div>
    );
  }

  return null;
}
