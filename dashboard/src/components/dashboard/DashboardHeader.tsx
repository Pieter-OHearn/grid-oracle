import { motion } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { SeasonSelector } from './SeasonSelector';

interface Props {
  season: number | null;
  completedCount: number;
  availableSeasons: number[];
  onSeasonChange: (season: number) => void;
}

export function DashboardHeader({
  season,
  completedCount,
  availableSeasons,
  onSeasonChange,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex items-center justify-between gap-3 mb-6"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-[#e10600]/15 border border-[#e10600]/30 flex items-center justify-center">
          <BarChart2 size={15} className="text-[#e10600]" />
        </div>
        <div>
          <h1
            className="text-white"
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: '1.5rem',
              fontWeight: 800,
              lineHeight: 1.1,
            }}
          >
            Season Accuracy Dashboard
          </h1>
          <p
            className="text-[#3a3a52] text-xs"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {season ?? '—'} F1 Season · Rounds 1–{completedCount} completed
          </p>
        </div>
      </div>
      {availableSeasons.length > 0 && season != null && (
        <SeasonSelector
          season={season}
          onChange={onSeasonChange}
          availableSeasons={availableSeasons}
        />
      )}
    </motion.div>
  );
}
