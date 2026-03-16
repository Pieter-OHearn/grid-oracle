import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart2, BarChart2 as EmptyIcon } from 'lucide-react';
import { api } from '../services/api';
import type { ApiAccuracyItem } from '../services/api';
import { DRIVERS, CONSTRUCTOR_COLORS, DRIVER_BY_NAME } from '../data';
import type { SeasonChartPoint } from '../types';
import type { BreakdownRow } from '../components/dashboard/PerRaceBreakdownTable';
import { StatCard } from '../components/common/StatCard';
import { AccuracyLineChart } from '../components/charts/AccuracyLineChart';
import { ExactHitBarChart } from '../components/charts/ExactHitBarChart';
import { PerRaceBreakdownTable } from '../components/dashboard/PerRaceBreakdownTable';
import { WinsTally } from '../components/dashboard/WinsTally';
import { SeasonSelector } from '../components/dashboard/SeasonSelector';

function buildChartData(items: ApiAccuracyItem[]): SeasonChartPoint[] {
  return items.map((item, idx) => ({
    race: item.race_name.replace(' Grand Prix', '').slice(0, 3).toUpperCase(),
    round: idx + 1,
    top3: Math.round((item.top3_accuracy ?? 0) * 100),
    top10: 0,
    exactHit: Math.round((item.exact_position_accuracy ?? 0) * 100),
    mpe: item.mean_position_error ?? 0,
    podiumCorrect: 0,
  }));
}

function buildBreakdownRows(items: ApiAccuracyItem[]): BreakdownRow[] {
  return items.map((item, idx) => {
    const driverCode = item.winner_name ? (DRIVER_BY_NAME[item.winner_name] ?? null) : null;
    const driver = driverCode ? DRIVERS[driverCode] : null;
    const shortName = item.race_name.replace(' Grand Prix', '');
    return {
      raceId: item.race_id,
      round: idx + 1,
      shortName: shortName.slice(0, 3).toUpperCase(),
      country: shortName,
      countryFlag: '🏁',
      top3Accuracy: item.top3_accuracy != null ? Math.round(item.top3_accuracy * 100) : undefined,
      top10Accuracy: undefined,
      exactHitRate:
        item.exact_position_accuracy != null
          ? Math.round(item.exact_position_accuracy * 100)
          : undefined,
      meanPositionError: item.mean_position_error ?? undefined,
      winnerShortName: driver?.shortName ?? item.winner_name ?? undefined,
      winnerColor: driver
        ? (CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280')
        : item.winner_constructor
          ? (CONSTRUCTOR_COLORS[item.winner_constructor] ?? '#6b7280')
          : undefined,
    };
  });
}

function buildWinnerCounts(items: ApiAccuracyItem[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    if (!item.winner_name) continue;
    const code = DRIVER_BY_NAME[item.winner_name] ?? item.winner_name;
    counts[code] = (counts[code] ?? 0) + 1;
  }
  return counts;
}

export function DashboardPage() {
  const [availableSeasons, setAvailableSeasons] = useState<number[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [accuracyData, setAccuracyData] = useState<ApiAccuracyItem[]>([]);
  const [totalRaces, setTotalRaces] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available seasons on mount
  useEffect(() => {
    api
      .getSeasons()
      .then((seasons) => {
        setAvailableSeasons(seasons);
        if (seasons.length) setSeason(seasons[0]);
      })
      .catch(() => setError('Failed to load seasons'));
  }, []);

  // Fetch accuracy + race list when season changes
  useEffect(() => {
    if (season == null) return;
    setLoading(true);
    setError(null);
    Promise.all([api.getSeasonAccuracy(season), api.getRaceList(season)])
      .then(([accuracy, races]) => {
        setAccuracyData(accuracy);
        setTotalRaces(races.length);
      })
      .catch(() => setError('Failed to load season data'))
      .finally(() => setLoading(false));
  }, [season]);

  const chartData = buildChartData(accuracyData);
  const rows = buildBreakdownRows(accuracyData);
  const winnerCounts = buildWinnerCounts(accuracyData);

  const evaluatedTop3 = accuracyData.filter((r) => r.top3_accuracy != null);
  const avgTop3 = evaluatedTop3.length
    ? Math.round(
        (evaluatedTop3.reduce((s, r) => s + r.top3_accuracy!, 0) / evaluatedTop3.length) * 100,
      )
    : 0;

  const evaluatedExact = accuracyData.filter((r) => r.exact_position_accuracy != null);
  const avgExact = evaluatedExact.length
    ? Math.round(
        (evaluatedExact.reduce((s, r) => s + r.exact_position_accuracy!, 0) /
          evaluatedExact.length) *
          100,
      )
    : 0;

  const evaluatedMPE = accuracyData.filter((r) => r.mean_position_error != null);
  const avgMPE = evaluatedMPE.length
    ? (evaluatedMPE.reduce((s, r) => s + r.mean_position_error!, 0) / evaluatedMPE.length).toFixed(
        2,
      )
    : '—';

  const bestItem = accuracyData.length
    ? accuracyData.reduce((best, r) =>
        (r.top3_accuracy ?? 0) > (best.top3_accuracy ?? 0) ? r : best,
      )
    : null;
  const bestRace = bestItem
    ? bestItem.race_name.replace(' Grand Prix', '').slice(0, 3).toUpperCase()
    : '—';

  const summaryStats = [
    {
      label: 'Races Analysed',
      value: accuracyData.length.toString(),
      icon: '🏎️',
      color: '#e10600',
      sub: totalRaces > 0 ? `of ${totalRaces} total` : 'races evaluated',
    },
    {
      label: 'Avg Podium Accuracy',
      value: `${avgTop3}%`,
      icon: '🏆',
      color: '#FFD700',
      sub: 'top 3 correct',
    },
    {
      label: 'Avg Exact Hit Rate',
      value: `${avgExact}%`,
      icon: '⚡',
      color: '#22c55e',
      sub: 'exact position',
    },
    {
      label: 'Avg Position Error',
      value: avgMPE,
      icon: '📐',
      color: '#f97316',
      sub: 'positions off',
    },
    {
      label: 'Best Race',
      value: bestRace,
      icon: '🎯',
      color: '#3b82f6',
      sub: bestItem ? `${Math.round((bestItem.top3_accuracy ?? 0) * 100)}% podium` : '—',
    },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between gap-3 mb-6"
      >
        <div className="flex items-center gap-3">
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
              {season ?? '—'} F1 Season · Rounds 1–{accuracyData.length} completed
            </p>
          </div>
        </div>
        {availableSeasons.length > 0 && season != null && (
          <SeasonSelector
            season={season}
            onChange={setSeason}
            availableSeasons={availableSeasons}
          />
        )}
      </motion.div>

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

          <PerRaceBreakdownTable rows={rows} />
          <WinsTally winnerCounts={winnerCounts} />
        </>
      )}
    </div>
  );
}
