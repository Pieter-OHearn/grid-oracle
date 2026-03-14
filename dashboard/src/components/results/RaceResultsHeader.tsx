import { motion } from 'framer-motion';
import type { Race } from '../../types';
import { formatDate } from '../../utils/results';

interface Props {
  race: Race;
}

export function RaceResultsHeader({ race }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mb-6"
    >
      <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 flex flex-col md:flex-row gap-4 items-start md:items-center">
        <div className="flex items-center gap-4 flex-1">
          <span className="text-4xl">{race.countryFlag}</span>
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className="px-2 py-0.5 bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded text-[10px] uppercase tracking-wider"
                style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
              >
                Race Concluded
              </span>
              <span
                className="text-[#3a3a52] text-[10px]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Round {String(race.round).padStart(2, '0')} · {formatDate(race.date)}
              </span>
            </div>
            <h1
              className="text-white"
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: '1.5rem',
                fontWeight: 800,
                lineHeight: 1.1,
              }}
            >
              {race.name}
            </h1>
            <p className="text-[#6b7280] text-xs mt-0.5">{race.circuit}</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
