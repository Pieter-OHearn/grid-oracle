import { motion } from 'framer-motion';
import { Calendar, MapPin } from 'lucide-react';
import type { AppRace } from '../../context/RaceListContext';
import { useRaceList } from '../../context/RaceListContext';
import { StatusBadge } from '../common/StatusBadge';
import { formatDate } from '../../utils/results';

interface Props {
  race: AppRace;
}

export function RaceResultsHeader({ race }: Props) {
  const { races } = useRaceList();

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mb-6"
    >
      <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 flex flex-col md:flex-row gap-4 items-start md:items-center">
        <div className="flex items-center gap-4 flex-1">
          <div className="text-5xl">{race.countryFlag}</div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={race.status} />
              <span
                className="text-[#3a3a52] text-[10px]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Round {String(race.round).padStart(2, '0')} / {races.length || 24}
              </span>
            </div>
            <h1
              className="text-white"
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: '1.6rem',
                fontWeight: 800,
                letterSpacing: '0.02em',
                lineHeight: 1.1,
              }}
            >
              {race.name}
            </h1>
            <div className="flex items-center gap-4 mt-1.5">
              <span className="flex items-center gap-1.5 text-[#6b7280] text-xs">
                <MapPin size={11} /> {race.city}
              </span>
              <span className="flex items-center gap-1.5 text-[#6b7280] text-xs">
                <Calendar size={11} /> {formatDate(race.date)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
