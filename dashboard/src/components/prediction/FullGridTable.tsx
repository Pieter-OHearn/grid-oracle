import { motion } from 'framer-motion';
import { TrendingUp, Zap } from 'lucide-react';
import type { PredictionEntry } from '../../types';
import { DRIVERS, CONSTRUCTOR_COLORS, CONSTRUCTOR_SHORT } from '../../data';
import { ConfidenceBar } from '../common/ConfidenceBar';
import { ModelNote } from '../common/ModelNote';
import { MEDAL_COLORS, getConfidenceColor, getConfidenceLabel } from '../../utils/predictions';

interface Props {
  predictions: PredictionEntry[];
}

export function FullGridTable({ predictions }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, delay: 0.15 }}
    >
      <div className="flex items-center gap-3 mb-3">
        <TrendingUp size={14} className="text-[#e10600]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          Full Grid Prediction
        </h2>
      </div>

      <div className="grid grid-cols-[40px_28px_1fr_80px_100px_80px] gap-3 px-4 py-2 mb-1">
        {['POS', '#', 'DRIVER', 'TEAM', 'CONFIDENCE', ''].map((h, i) => (
          <span
            key={i}
            className="text-[#3a3a52] text-[10px] uppercase tracking-wider"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
          >
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
              className="grid grid-cols-[40px_28px_1fr_80px_100px_80px] gap-3 items-center px-4 py-3 bg-[#0f0f1a] border border-[#1e1e30] rounded-lg hover:border-[#2a2a40] hover:bg-[#121220] transition-all duration-150"
              style={{ borderLeft: `3px solid ${teamColor}` }}
            >
              <span
                className="text-white"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: entry.position <= 3 ? '1.1rem' : '0.9rem',
                  fontWeight: 800,
                  color: entry.position <= 3 ? MEDAL_COLORS[entry.position - 1] : '#9090a8',
                }}
              >
                P{entry.position}
              </span>
              <span
                className="text-center text-xs"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontWeight: 600,
                  color: teamColor,
                }}
              >
                {driver.number}
              </span>
              <div className="min-w-0">
                <span
                  className="text-white text-sm block truncate"
                  style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontWeight: entry.position <= 3 ? 700 : 600,
                    letterSpacing: '0.03em',
                  }}
                >
                  {driver.name}
                </span>
                <span
                  className="text-[#3a3a52] text-[10px]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {driver.flag} {driver.nationality}
                </span>
              </div>
              <div className="flex items-center gap-1.5 min-w-0">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: teamColor }}
                />
                <span
                  className="text-[#6b7280] text-[10px] truncate"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                >
                  {CONSTRUCTOR_SHORT[driver.constructor]}
                </span>
              </div>
              <ConfidenceBar
                confidence={entry.confidence}
                color={confColor}
                delay={0.25 + idx * 0.025}
              />
              <div className="flex items-center gap-1.5">
                {entry.position <= 3 && <Zap size={10} style={{ color: confColor }} />}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '0.7rem',
                    color: confColor,
                    fontWeight: 600,
                  }}
                >
                  {entry.confidence}% {getConfidenceLabel(entry.confidence)}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>

      <ModelNote
        text="Predictions generated by GridOracle ML v2.4.1 · Confidence scores represent the model's probability estimate for each driver finishing in the stated position · Updated 4h before lights out"
        variant="zap"
      />
    </motion.div>
  );
}
