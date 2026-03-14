import { motion } from 'framer-motion';
import { Target } from 'lucide-react';
import { useNavigate } from 'react-router';
import type { Race } from '../../types';
import { RACE_ACCURACY, RACE_RESULTS, DRIVERS, CONSTRUCTOR_COLORS } from '../../data';

interface Props {
  completedRaces: Race[];
}

export function PerRaceBreakdownTable({ completedRaces }: Props) {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.2 }}
      className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl overflow-hidden"
    >
      <div className="flex items-center gap-2 px-5 py-4 border-b border-[#1e1e30]">
        <Target size={13} className="text-[#e10600]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          Per-Race Breakdown
        </h2>
      </div>

      <div className="grid grid-cols-[32px_1fr_90px_90px_90px_90px_80px] gap-4 px-5 py-2.5 border-b border-[#1e1e30]">
        {['#', 'RACE', 'PODIUM', 'TOP 10', 'EXACT', 'MPE', 'WINNER'].map((h) => (
          <span
            key={h}
            className="text-[10px] uppercase tracking-wider text-[#3a3a52]"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
          >
            {h}
          </span>
        ))}
      </div>

      {completedRaces.map((race, idx) => {
        const acc = RACE_ACCURACY[race.id];
        const results = RACE_RESULTS[race.id];
        const winner = results?.find((r) => r.position === 1);
        const winnerDriver = winner ? DRIVERS[winner.driverId] : null;
        const winnerColor = winnerDriver
          ? (CONSTRUCTOR_COLORS[winnerDriver.constructor] ?? '#6b7280')
          : '#6b7280';

        return (
          <motion.div
            key={race.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25, delay: 0.25 + idx * 0.03 }}
            onClick={() => navigate(`/race/${race.id}/results`)}
            className="grid grid-cols-[32px_1fr_90px_90px_90px_90px_80px] gap-4 px-5 py-3 border-b border-[#1a1a28] hover:bg-[#131320] cursor-pointer transition-colors group"
          >
            <span
              className="text-[#3a3a52] text-xs"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {String(race.round).padStart(2, '0')}
            </span>
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-base">{race.countryFlag}</span>
              <span
                className="text-white text-sm truncate group-hover:text-[#e10600] transition-colors"
                style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
              >
                {race.shortName} — {race.country}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-1 flex-1 bg-[#1e1e30] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${acc?.top3Accuracy ?? 0}%`,
                    background:
                      (acc?.top3Accuracy ?? 0) === 100
                        ? '#22c55e'
                        : (acc?.top3Accuracy ?? 0) >= 67
                          ? '#eab308'
                          : '#ef4444',
                  }}
                />
              </div>
              <span
                className="text-xs flex-shrink-0"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  color:
                    (acc?.top3Accuracy ?? 0) === 100
                      ? '#22c55e'
                      : (acc?.top3Accuracy ?? 0) >= 67
                        ? '#eab308'
                        : '#ef4444',
                }}
              >
                {acc?.top3Accuracy}%
              </span>
            </div>
            <span
              className="text-xs"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: (acc?.top10Accuracy ?? 0) >= 70 ? '#22c55e' : '#eab308',
              }}
            >
              {acc?.top10Accuracy}%
            </span>
            <span
              className="text-xs"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color:
                  (acc?.exactHitRate ?? 0) >= 25
                    ? '#22c55e'
                    : (acc?.exactHitRate ?? 0) >= 15
                      ? '#eab308'
                      : '#ef4444',
              }}
            >
              {acc?.exactHitRate}%
            </span>
            <span
              className="text-xs"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color:
                  (acc?.meanPositionError ?? 99) <= 2
                    ? '#22c55e'
                    : (acc?.meanPositionError ?? 99) <= 3
                      ? '#eab308'
                      : '#ef4444',
              }}
            >
              {acc?.meanPositionError.toFixed(1)}
            </span>
            {winnerDriver && (
              <div className="flex items-center gap-1.5 min-w-0">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: winnerColor }}
                />
                <span
                  className="text-[#9090a8] text-[10px] truncate"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                >
                  {winnerDriver.shortName}
                </span>
              </div>
            )}
          </motion.div>
        );
      })}
    </motion.div>
  );
}
