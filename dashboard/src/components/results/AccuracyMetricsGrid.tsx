import { motion } from 'framer-motion';
import type { AccuracyMetrics } from '../../types';

interface Props {
  accuracy: AccuracyMetrics;
}

export function AccuracyMetricsGrid({ accuracy }: Props) {
  const metrics = [
    {
      label: 'Podium Accuracy',
      value: `${accuracy.top3Accuracy}%`,
      sub: `${accuracy.podiumCorrect}/3 correct`,
      icon: '🏆',
      color: '#FFD700',
    },
    {
      label: 'Top 5 Accuracy',
      value: `${accuracy.top5Accuracy}%`,
      sub: 'Drivers in top 5',
      icon: '🎯',
      color: '#22c55e',
    },
    {
      label: 'Top 10 Accuracy',
      value: `${accuracy.top10Accuracy}%`,
      sub: 'Points positions',
      icon: '📊',
      color: '#3b82f6',
    },
    {
      label: 'Exact Hit Rate',
      value: `${accuracy.exactHitRate}%`,
      sub: 'Perfect position calls',
      icon: '⚡',
      color: '#e10600',
    },
    {
      label: 'Mean Pos. Error',
      value: accuracy.meanPositionError.toFixed(1),
      sub: 'Avg positions off',
      icon: '📐',
      color: '#f97316',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.05 }}
      className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6"
    >
      {metrics.map((m, i) => (
        <motion.div
          key={m.label}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.1 + i * 0.05 }}
          className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center"
        >
          <div className="text-xl mb-1">{m.icon}</div>
          <div
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: '1.6rem',
              fontWeight: 800,
              color: m.color,
              lineHeight: 1,
            }}
          >
            {m.value}
          </div>
          <div
            className="text-[#3a3a52] text-[10px] mt-1 uppercase tracking-wider"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
          >
            {m.label}
          </div>
          <div
            className="text-[#4a4a62] text-[9px] mt-0.5"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {m.sub}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
