import { motion } from 'framer-motion';
import { Calendar, MapPin } from 'lucide-react';
import type { Race, PredictionEntry } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { getConfidenceColor, formatDate } from '../../utils/predictions';

interface Props {
  race: Race;
  predictions: PredictionEntry[];
}

export function RaceHero({ race, predictions }: Props) {
  const avgConfidence = Math.round(
    predictions.reduce((s, p) => s + p.confidence, 0) / predictions.length,
  );
  const topConfidence = predictions[0]?.confidence ?? 0;

  const stats = [
    {
      label: 'Top Confidence',
      value: `${topConfidence}%`,
      color: getConfidenceColor(topConfidence),
    },
    {
      label: 'Avg Confidence',
      value: `${avgConfidence}%`,
      color: getConfidenceColor(avgConfidence),
    },
    { label: 'Drivers', value: `${predictions.length}`, color: '#ffffff' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mb-6"
    >
      <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 flex flex-col md:flex-row md:items-center gap-4">
        <div className="flex items-center gap-4 flex-1">
          <div className="text-5xl">{race.countryFlag}</div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={race.status} />
              <span
                className="text-[#3a3a52] text-[10px]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Round {String(race.round).padStart(2, '0')} / 24
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
                <MapPin size={11} /> {race.circuit}
              </span>
              <span className="flex items-center gap-1.5 text-[#6b7280] text-xs">
                <Calendar size={11} /> {formatDate(race.date)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex gap-4 md:gap-6">
          {stats.map((stat, i) => (
            <div
              key={stat.label}
              className={
                i > 0 ? 'text-center border-l border-[#1e1e30] pl-4 md:pl-6' : 'text-center'
              }
            >
              <p
                className="text-[#3a3a52] text-[10px] uppercase tracking-wider mb-0.5"
                style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
              >
                {stat.label}
              </p>
              <p
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: '1.5rem',
                  fontWeight: 800,
                  color: stat.color,
                }}
              >
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
