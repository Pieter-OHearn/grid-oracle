import { motion } from 'framer-motion';
import type { Row } from '../../types';
import { DRIVERS, CONSTRUCTOR_COLORS, CONSTRUCTOR_SHORT } from '../../data';
import { DeltaIndicator } from '../common/DeltaIndicator';
import { getDeltaBg, getDeltaBorder } from '../../utils/results';

const MEDAL_COLORS = ['#FFD700', '#C0C0C0', '#CD7F32'];

interface Props {
  rows: Row[];
}

export function ComparisonRows({ rows }: Props) {
  return (
    <div className="space-y-1.5">
      {rows.map(({ result, prediction, predictedPos, delta }, idx) => {
        const driver = DRIVERS[result.driverId];
        if (!driver) return null;
        const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';

        return (
          <motion.div
            key={result.driverId}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: 0.15 + idx * 0.022 }}
            className="grid grid-cols-[1fr_44px_1fr] gap-2 items-center"
          >
            {/* Predicted */}
            <div
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
              style={{ background: getDeltaBg(delta), borderColor: getDeltaBorder(delta) }}
            >
              <span
                className="flex-shrink-0 w-8 text-center"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: '1rem',
                  fontWeight: 800,
                  color:
                    predictedPos && predictedPos <= 3 ? MEDAL_COLORS[predictedPos - 1] : '#6b7280',
                }}
              >
                {predictedPos ? `P${predictedPos}` : '?'}
              </span>
              <div className="w-px h-6 bg-[#1e1e30]" />
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className="w-1.5 h-5 rounded-sm flex-shrink-0"
                  style={{ background: teamColor }}
                />
                <div className="min-w-0">
                  <span
                    className="text-white text-sm block truncate"
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontWeight: 700,
                      letterSpacing: '0.02em',
                    }}
                  >
                    {driver.name}
                  </span>
                  <span
                    className="text-[#4a4a62] text-[10px]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {CONSTRUCTOR_SHORT[driver.constructor]}
                  </span>
                </div>
              </div>
              {prediction && (
                <span
                  className="ml-auto text-[10px] flex-shrink-0"
                  style={{ fontFamily: "'JetBrains Mono', monospace", color: '#4a4a62' }}
                >
                  {prediction.confidence}%
                </span>
              )}
            </div>

            <DeltaIndicator delta={delta} />

            {/* Actual */}
            <div
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
              style={{ background: getDeltaBg(delta), borderColor: getDeltaBorder(delta) }}
            >
              <span
                className="flex-shrink-0 w-8 text-center"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: '1rem',
                  fontWeight: 800,
                  color: result.position <= 3 ? MEDAL_COLORS[result.position - 1] : '#9090a8',
                }}
              >
                {result.dnf ? 'DNF' : `P${result.position}`}
              </span>
              <div className="w-px h-6 bg-[#1e1e30]" />
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <div
                  className="w-1.5 h-5 rounded-sm flex-shrink-0"
                  style={{ background: teamColor }}
                />
                <div className="min-w-0">
                  <span
                    className="text-white text-sm block truncate"
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontWeight: 700,
                      letterSpacing: '0.02em',
                    }}
                  >
                    {driver.name}
                  </span>
                  <span
                    className="text-[#4a4a62] text-[10px]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {result.dnf ? (result.dnfReason ?? 'DNF') : result.time}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 ml-auto flex-shrink-0">
                {result.fastestLap && (
                  <span
                    className="px-1.5 py-0.5 bg-[#a855f7]/20 text-[#a855f7] border border-[#a855f7]/30 rounded text-[9px] uppercase"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                  >
                    FL
                  </span>
                )}
                {result.dnf && (
                  <span
                    className="px-1.5 py-0.5 bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/30 rounded text-[9px] uppercase"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                  >
                    DNF
                  </span>
                )}
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
