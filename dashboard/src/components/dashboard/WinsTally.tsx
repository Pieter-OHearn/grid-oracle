import { motion } from 'framer-motion';
import { Award } from 'lucide-react';
import { DRIVERS, CONSTRUCTOR_COLORS } from '../../data';

interface Props {
  winnerCounts: Record<string, number>;
}

export function WinsTally({ winnerCounts }: Props) {
  const entries = Object.entries(winnerCounts).sort((a, b) => b[1] - a[1]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.3 }}
      className="mt-4 bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5"
    >
      <div className="flex items-center gap-2 mb-4">
        <Award size={13} className="text-[#FFD700]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          Race Wins So Far
        </h2>
      </div>
      {entries.length === 0 ? (
        <p className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          No winner data available
        </p>
      ) : (
        <div className="flex flex-wrap gap-3">
          {entries.map(([driverId, wins]) => {
            const driver = DRIVERS[driverId];
            if (!driver) return null;
            const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';
            return (
              <div
                key={driverId}
                className="flex items-center gap-2 px-3 py-2 bg-[#131320] border border-[#1e1e30] rounded-lg"
              >
                <div className="w-2 h-2 rounded-full" style={{ background: teamColor }} />
                <span
                  className="text-white text-xs"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                >
                  {driver.shortName}
                </span>
                <span
                  className="text-[#3a3a52] text-[10px]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {driver.constructor}
                </span>
                <span
                  className="text-[#FFD700] ml-1"
                  style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontSize: '0.9rem',
                    fontWeight: 800,
                  }}
                >
                  {wins}W
                </span>
              </div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
