import type { ApiAccuracyItem, ApiRaceListItem } from '../services/api';
import type { SeasonChartPoint } from '../types';
import type { BreakdownRow } from '../components/dashboard/PerRaceBreakdownTable';
import { DRIVERS, CONSTRUCTOR_COLORS, DRIVER_BY_NAME } from '../data';
import { getCountryFlag } from './countryFlags';

export interface SummaryStatItem {
  label: string;
  value: string;
  icon: string;
  color: string;
  sub: string;
}

export function buildChartData(items: ApiAccuracyItem[]): SeasonChartPoint[] {
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

export function buildBreakdownRows(
  items: ApiAccuracyItem[],
  raceList: ApiRaceListItem[],
): BreakdownRow[] {
  const raceById = new Map(raceList.map((r) => [r.id, r]));
  return items.map((item, idx) => {
    const raceInfo = raceById.get(item.race_id);
    const country = raceInfo?.country ?? item.race_name.replace(' Grand Prix', '');
    const driverCode = item.winner_name ? (DRIVER_BY_NAME[item.winner_name] ?? null) : null;
    const driver = driverCode ? DRIVERS[driverCode] : null;
    return {
      raceId: item.race_id,
      round: raceInfo?.round ?? idx + 1,
      shortName: country.slice(0, 3).toUpperCase(),
      country,
      countryFlag: getCountryFlag(country),
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

export function buildWinnerCounts(items: ApiAccuracyItem[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    if (!item.winner_name) continue;
    const code = DRIVER_BY_NAME[item.winner_name] ?? item.winner_name;
    counts[code] = (counts[code] ?? 0) + 1;
  }
  return counts;
}

export function buildSummaryStats(
  accuracyData: ApiAccuracyItem[],
  totalRaces: number,
): SummaryStatItem[] {
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

  return [
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
}
