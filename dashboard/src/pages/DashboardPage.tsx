import { motion } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { RACE_ACCURACY } from '../data';
import { StatCard } from '../components/common/StatCard';
import { AccuracyLineChart } from '../components/charts/AccuracyLineChart';
import { ExactHitBarChart } from '../components/charts/ExactHitBarChart';
import { PerRaceBreakdownTable } from '../components/dashboard/PerRaceBreakdownTable';
import { WinsTally } from '../components/dashboard/WinsTally';
import {
  completedRaces,
  winnerCounts,
  seasonAvgTop3,
  seasonAvgExact,
  seasonAvgMPE,
  bestRace,
} from '../utils/season';

export function DashboardPage() {
  const summaryStats = [
    {
      label: 'Races Analysed',
      value: completedRaces.length.toString(),
      icon: '🏎️',
      color: '#e10600',
      sub: 'of 24 total',
    },
    {
      label: 'Avg Podium Accuracy',
      value: `${seasonAvgTop3}%`,
      icon: '🏆',
      color: '#FFD700',
      sub: 'top 3 correct',
    },
    {
      label: 'Avg Exact Hit Rate',
      value: `${seasonAvgExact}%`,
      icon: '⚡',
      color: '#22c55e',
      sub: 'exact position',
    },
    {
      label: 'Avg Position Error',
      value: seasonAvgMPE,
      icon: '📐',
      color: '#f97316',
      sub: 'positions off',
    },
    {
      label: 'Best Race',
      value: bestRace?.shortName ?? '—',
      icon: '🎯',
      color: '#3b82f6',
      sub: bestRace ? `${RACE_ACCURACY[bestRace.id]?.top3Accuracy ?? 0}% podium` : '—',
    },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-3 mb-6"
      >
        <div className="w-8 h-8 rounded-lg bg-[#e10600]/15 border border-[#e10600]/30 flex items-center justify-center">
          <BarChart2 size={15} className="text-[#e10600]" />
        </div>
        <div>
          <h1
            className="text-white"
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: '1.5rem',
              fontWeight: 800,
              lineHeight: 1.1,
            }}
          >
            Season Accuracy Dashboard
          </h1>
          <p
            className="text-[#3a3a52] text-xs"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            2025 F1 Season · Rounds 1–{completedRaces.length} completed
          </p>
        </div>
      </motion.div>

      {/* Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6"
      >
        {summaryStats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.08 + i * 0.05 }}
          >
            <StatCard label={s.label} value={s.value} sub={s.sub} icon={s.icon} color={s.color} />
          </motion.div>
        ))}
      </motion.div>

      {/* Charts */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
      >
        <AccuracyLineChart />
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.15 }}
      >
        <ExactHitBarChart />
      </motion.div>

      <PerRaceBreakdownTable completedRaces={completedRaces} />
      <WinsTally winnerCounts={winnerCounts} />
    </div>
  );
}
