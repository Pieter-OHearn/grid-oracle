import { ChevronDown } from 'lucide-react';

interface Props {
  season: number;
  onChange: (season: number) => void;
  availableSeasons?: number[];
}

const DEFAULT_SEASONS = [2025, 2024];

export function SeasonSelector({ season, onChange, availableSeasons = DEFAULT_SEASONS }: Props) {
  return (
    <div className="relative">
      <select
        value={season}
        onChange={(e) => onChange(Number(e.target.value))}
        className="appearance-none bg-[#131320] border border-[#1e1e30] rounded-lg pl-3 pr-8 py-1.5 text-white text-xs cursor-pointer hover:border-[#2a2a40] transition-colors focus:outline-none focus:border-[#e10600]/50"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {availableSeasons.map((y) => (
          <option key={y} value={y}>
            {y} Season
          </option>
        ))}
      </select>
      <ChevronDown
        size={12}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none"
      />
    </div>
  );
}
