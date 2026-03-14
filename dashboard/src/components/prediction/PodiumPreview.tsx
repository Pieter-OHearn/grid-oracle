import { motion } from 'framer-motion';
import type { PredictionEntry } from '../../types';
import { ConfidenceBar } from '../common/ConfidenceBar';
import { DRIVERS, CONSTRUCTOR_COLORS } from '../../data';
import {
  PODIUM_ORDER,
  MEDAL_COLORS,
  getConfidenceColor,
  getConfidenceLabel,
} from '../../utils/predictions';

interface Props {
  predictions: PredictionEntry[];
}

export function PodiumPreview({ predictions }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.05 }}
      className="grid grid-cols-3 gap-3 mb-6"
    >
      {PODIUM_ORDER.map((offset, idx) => {
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
            className={heightClass}
          >
            <div
              className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center relative overflow-hidden"
              style={{ borderTop: `3px solid ${teamColor}` }}
            >
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: `radial-gradient(ellipse at top, ${teamColor}08, transparent 70%)`,
                }}
              />
              <div className="relative">
                <div
                  className="text-[#3a3a52] text-xs mb-1"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                >
                  {podiumPos === 1 ? 'P1 · PREDICTED WINNER' : `P${podiumPos} · PREDICTED`}
                </div>
                <div
                  className="text-white mb-0.5"
                  style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontSize: podiumPos === 1 ? '1.2rem' : '1rem',
                    fontWeight: 800,
                    lineHeight: 1.1,
                  }}
                >
                  {driver.name}
                </div>
                <div className="flex items-center justify-center gap-1.5 mb-3">
                  <div className="w-2 h-2 rounded-full" style={{ background: teamColor }} />
                  <span
                    className="text-[#6b7280] text-[10px]"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                  >
                    {driver.constructor}
                  </span>
                </div>
                <ConfidenceBar
                  confidence={entry.confidence}
                  color={teamColor}
                  delay={0.3 + idx * 0.1}
                  height="h-1"
                />
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '0.7rem',
                    color: getConfidenceColor(entry.confidence),
                  }}
                >
                  {entry.confidence}% {getConfidenceLabel(entry.confidence)}
                </span>
              </div>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

export { MEDAL_COLORS };
