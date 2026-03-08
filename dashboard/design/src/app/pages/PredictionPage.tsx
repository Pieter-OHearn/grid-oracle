import { useParams } from 'react-router';
import { motion } from 'motion/react';
import { Calendar, MapPin, Zap, TrendingUp, AlertCircle } from 'lucide-react';
import { RACES, DRIVERS, RACE_PREDICTIONS, CONSTRUCTOR_COLORS, CONSTRUCTOR_SHORT } from '../data/mockData';

function getConfidenceColor(confidence: number): string {
  if (confidence >= 70) return '#22c55e';
  if (confidence >= 55) return '#84cc16';
  if (confidence >= 40) return '#eab308';
  if (confidence >= 25) return '#f97316';
  return '#ef4444';
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 70) return 'HIGH';
  if (confidence >= 55) return 'STRONG';
  if (confidence >= 40) return 'MODERATE';
  if (confidence >= 25) return 'LOW';
  return 'VERY LOW';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function PredictionPage() {
  const { raceId } = useParams();
  const race = RACES.find(r => r.id === raceId);
  const predictions = raceId ? RACE_PREDICTIONS[raceId] : null;

  if (!race) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <div className="text-center">
          <AlertCircle size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Race not found</p>
        </div>
      </div>
    );
  }

  if (!predictions) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <p className="text-sm">No prediction data available for this race.</p>
      </div>
    );
  }

  const avgConfidence = Math.round(predictions.reduce((s, p) => s + p.confidence, 0) / predictions.length);
  const topConfidence = predictions[0]?.confidence ?? 0;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Race Hero */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="mb-6"
      >
        <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 flex flex-col md:flex-row md:items-center gap-4">
          {/* Flag + race info */}
          <div className="flex items-center gap-4 flex-1">
            <div className="text-5xl">{race.countryFlag}</div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                {race.status === 'next' && (
                  <span className="px-2 py-0.5 bg-[#e10600]/20 text-[#e10600] border border-[#e10600]/40 rounded text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                    Next Race
                  </span>
                )}
                {race.status === 'upcoming' && (
                  <span className="px-2 py-0.5 bg-[#1e1e30] text-[#6b7280] rounded text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                    Upcoming
                  </span>
                )}
                {race.status === 'completed' && (
                  <span className="px-2 py-0.5 bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                    Completed
                  </span>
                )}
                <span className="text-[#3a3a52] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  Round {String(race.round).padStart(2, '0')} / 24
                </span>
              </div>
              <h1 className="text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.6rem', fontWeight: 800, letterSpacing: '0.02em', lineHeight: 1.1 }}>
                {race.name}
              </h1>
              <div className="flex items-center gap-4 mt-1.5">
                <span className="flex items-center gap-1.5 text-[#6b7280] text-xs">
                  <MapPin size={11} />
                  {race.circuit}
                </span>
                <span className="flex items-center gap-1.5 text-[#6b7280] text-xs">
                  <Calendar size={11} />
                  {formatDate(race.date)}
                </span>
              </div>
            </div>
          </div>

          {/* Stats row */}
          <div className="flex gap-4 md:gap-6">
            <div className="text-center">
              <p className="text-[#3a3a52] text-[10px] uppercase tracking-wider mb-0.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Top Confidence</p>
              <p className="text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.5rem', fontWeight: 800, color: getConfidenceColor(topConfidence) }}>
                {topConfidence}%
              </p>
            </div>
            <div className="w-px bg-[#1e1e30]" />
            <div className="text-center">
              <p className="text-[#3a3a52] text-[10px] uppercase tracking-wider mb-0.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Avg Confidence</p>
              <p style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.5rem', fontWeight: 800, color: getConfidenceColor(avgConfidence) }}>
                {avgConfidence}%
              </p>
            </div>
            <div className="w-px bg-[#1e1e30]" />
            <div className="text-center">
              <p className="text-[#3a3a52] text-[10px] uppercase tracking-wider mb-0.5" style={{ fontFamily: "'Barlow Condensed', sans-serif" }}>Drivers</p>
              <p className="text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.5rem', fontWeight: 800 }}>
                {predictions.length}
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Podium Preview */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        className="grid grid-cols-3 gap-3 mb-6"
      >
        {[1, 0, 2].map((offset, idx) => {
          const entry = predictions[offset];
          if (!entry) return null;
          const driver = DRIVERS[entry.driverId];
          if (!driver) return null;
          const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';
          const podiumPos = offset + 1;
          const heightClass = offset === 0 ? 'pt-0' : offset === 1 ? 'pt-4' : 'pt-8';
          return (
            <motion.div
              key={entry.driverId}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 + idx * 0.07 }}
              className={`${heightClass}`}
            >
              <div
                className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center relative overflow-hidden"
                style={{ borderTop: `3px solid ${teamColor}` }}
              >
                {/* Subtle glow */}
                <div className="absolute inset-0 pointer-events-none" style={{ background: `radial-gradient(ellipse at top, ${teamColor}08, transparent 70%)` }} />
                <div className="relative">
                  <div className="text-[#3a3a52] text-xs mb-1" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                    {podiumPos === 1 ? 'P1 · PREDICTED WINNER' : podiumPos === 2 ? 'P2 · PREDICTED' : 'P3 · PREDICTED'}
                  </div>
                  <div
                    className="text-white mb-0.5"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: podiumPos === 1 ? '1.2rem' : '1rem', fontWeight: 800, lineHeight: 1.1 }}
                  >
                    {driver.name}
                  </div>
                  <div className="flex items-center justify-center gap-1.5 mb-3">
                    <div className="w-2 h-2 rounded-full" style={{ background: teamColor }} />
                    <span className="text-[#6b7280] text-[10px]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                      {driver.constructor}
                    </span>
                  </div>
                  {/* Confidence bar */}
                  <div className="h-1 rounded-full bg-[#1e1e30] overflow-hidden mb-1.5">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${entry.confidence}%` }}
                      transition={{ duration: 0.8, delay: 0.3 + idx * 0.1, ease: 'easeOut' }}
                      className="h-full rounded-full"
                      style={{ background: `linear-gradient(90deg, ${teamColor}80, ${teamColor})` }}
                    />
                  </div>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem', color: getConfidenceColor(entry.confidence) }}>
                    {entry.confidence}% {getConfidenceLabel(entry.confidence)}
                  </span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Full Grid */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.15 }}
      >
        <div className="flex items-center gap-3 mb-3">
          <TrendingUp size={14} className="text-[#e10600]" />
          <h2 className="text-xs uppercase tracking-wider text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}>
            Full Grid Prediction
          </h2>
        </div>

        {/* Header row */}
        <div className="grid grid-cols-[40px_28px_1fr_80px_100px_80px] gap-3 px-4 py-2 mb-1">
          {['POS', '#', 'DRIVER', 'TEAM', 'CONFIDENCE', ''].map((h, i) => (
            <span key={i} className="text-[#3a3a52] text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
              {h}
            </span>
          ))}
        </div>

        <div className="space-y-1">
          {predictions.map((entry, idx) => {
            const driver = DRIVERS[entry.driverId];
            if (!driver) return null;
            const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';
            const confColor = getConfidenceColor(entry.confidence);

            return (
              <motion.div
                key={entry.driverId}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: 0.18 + idx * 0.025 }}
                className="grid grid-cols-[40px_28px_1fr_80px_100px_80px] gap-3 items-center px-4 py-3 bg-[#0f0f1a] border border-[#1e1e30] rounded-lg hover:border-[#2a2a40] hover:bg-[#121220] transition-all duration-150 group"
                style={{ borderLeft: `3px solid ${teamColor}` }}
              >
                {/* Position */}
                <span
                  className="text-white"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: entry.position <= 3 ? '1.1rem' : '0.9rem', fontWeight: 800, color: entry.position === 1 ? '#FFD700' : entry.position === 2 ? '#C0C0C0' : entry.position === 3 ? '#CD7F32' : '#9090a8' }}
                >
                  P{entry.position}
                </span>

                {/* Driver number */}
                <span
                  className="text-center text-xs"
                  style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: teamColor }}
                >
                  {driver.number}
                </span>

                {/* Driver name */}
                <div className="min-w-0">
                  <span
                    className="text-white text-sm block truncate group-hover:text-white"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: entry.position <= 3 ? 700 : 600, letterSpacing: '0.03em' }}
                  >
                    {driver.name}
                  </span>
                  <span className="text-[#3a3a52] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {driver.flag} {driver.nationality}
                  </span>
                </div>

                {/* Constructor */}
                <div className="flex items-center gap-1.5 min-w-0">
                  <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: teamColor }} />
                  <span className="text-[#6b7280] text-[10px] truncate" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                    {CONSTRUCTOR_SHORT[driver.constructor]}
                  </span>
                </div>

                {/* Confidence bar */}
                <div>
                  <div className="h-1.5 bg-[#1e1e30] rounded-full overflow-hidden mb-1">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${entry.confidence}%` }}
                      transition={{ duration: 0.7, delay: 0.25 + idx * 0.025, ease: 'easeOut' }}
                      className="h-full rounded-full"
                      style={{ background: `linear-gradient(90deg, ${confColor}60, ${confColor})` }}
                    />
                  </div>
                </div>

                {/* Confidence value */}
                <div className="flex items-center gap-1.5">
                  {entry.position <= 3 && <Zap size={10} style={{ color: confColor }} />}
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem', color: confColor, fontWeight: 600 }}>
                    {entry.confidence}%
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Model note */}
        <div className="mt-6 px-4 py-3 bg-[#0f0f1a] border border-[#1e1e30] rounded-lg flex items-start gap-3">
          <Zap size={13} className="text-[#e10600] mt-0.5 flex-shrink-0" />
          <p className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            Predictions generated by GridOracle ML v2.4.1 · Confidence scores represent the model's probability estimate for each driver finishing in the stated position · Updated 4h before lights out
          </p>
        </div>
      </motion.div>
    </div>
  );
}