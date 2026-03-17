import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart2 as EmptyIcon } from 'lucide-react';
import { api } from '../services/api';
import type { ApiAccuracyItem, ApiModelVersionItem, ApiRaceListItem } from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { AccuracyLineChart } from '../components/charts/AccuracyLineChart';
import { ExactHitBarChart } from '../components/charts/ExactHitBarChart';
import { LearningCurveChart } from '../components/accuracy/LearningCurveChart';
import { PerRaceBreakdownTable } from '../components/dashboard/PerRaceBreakdownTable';
import { WinsTally } from '../components/dashboard/WinsTally';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import {
  buildChartData,
  buildBreakdownRows,
  buildLearningCurveData,
  buildWinnerCounts,
  buildSummaryStats,
} from '../utils/dashboard';

export function DashboardPage() {
  const [availableSeasons, setAvailableSeasons] = useState<number[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [accuracyData, setAccuracyData] = useState<ApiAccuracyItem[]>([]);
  const [raceList, setRaceList] = useState<ApiRaceListItem[]>([]);
  const [modelVersions, setModelVersions] = useState<ApiModelVersionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available seasons on mount
  useEffect(() => {
    api
      .getSeasons()
      .then((seasons) => {
        setAvailableSeasons(seasons);
        if (seasons.length) {
          setSeason(seasons[0]);
        } else {
          setLoading(false);
        }
      })
      .catch(() => {
        setError('Failed to load seasons');
        setLoading(false);
      });
  }, []);

  // Fetch accuracy + race list when season changes
  useEffect(() => {
    if (season == null) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.getSeasonAccuracy(season),
      api.getRaceList(season),
      api.getModelVersions(season),
    ])
      .then(([accuracy, races, versions]) => {
        setAccuracyData(accuracy);
        setRaceList(races);
        setModelVersions(versions);
      })
      .catch(() => setError('Failed to load season data'))
      .finally(() => setLoading(false));
  }, [season]);

  const chartData = buildChartData(accuracyData);
  const learningCurveData = buildLearningCurveData(modelVersions);
  const rows = buildBreakdownRows(accuracyData, raceList);
  const winnerCounts = buildWinnerCounts(accuracyData);
  const summaryStats = buildSummaryStats(accuracyData, raceList.length);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <DashboardHeader
        season={season}
        completedCount={accuracyData.length}
        availableSeasons={availableSeasons}
        onSeasonChange={setSeason}
      />

      {loading && (
        <div className="flex items-center justify-center py-24">
          <div
            className="text-[#3a3a52] text-sm"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            Loading season data…
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="flex items-center justify-center py-24">
          <div
            className="text-[#ef4444] text-sm"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {error}
          </div>
        </div>
      )}

      {!loading && !error && accuracyData.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex flex-col items-center justify-center py-24 gap-4"
        >
          <div className="w-12 h-12 rounded-xl bg-[#0f0f1a] border border-[#1e1e30] flex items-center justify-center">
            <EmptyIcon size={20} className="text-[#3a3a52]" />
          </div>
          <div className="text-center">
            <p
              className="text-[#6b7280] text-sm mb-1"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
            >
              No races evaluated yet
            </p>
            <p
              className="text-[#3a3a52] text-xs"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              Accuracy data will appear here after races are completed and evaluated.
            </p>
          </div>
        </motion.div>
      )}

      {!loading && !error && accuracyData.length > 0 && (
        <>
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
                <StatCard
                  label={s.label}
                  value={s.value}
                  sub={s.sub}
                  icon={s.icon}
                  color={s.color}
                />
              </motion.div>
            ))}
          </motion.div>

          {/* Charts */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 }}
          >
            <AccuracyLineChart data={chartData} />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.15 }}
          >
            <ExactHitBarChart data={chartData} />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.2 }}
          >
            <LearningCurveChart data={learningCurveData} />
          </motion.div>

          <PerRaceBreakdownTable rows={rows} />
          <WinsTally winnerCounts={winnerCounts} />
        </>
      )}
    </div>
  );
}
