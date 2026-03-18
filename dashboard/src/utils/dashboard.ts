import type { ApiAccuracyItem, ApiModelVersionItem, ApiRaceListItem } from '../services/api';
import type { LearningCurvePoint, SeasonChartPoint } from '../types';
import type { BreakdownRow } from '../components/dashboard/PerRaceBreakdownTable';
import { CONSTRUCTOR_COLORS } from '../data';
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
      winnerShortName: item.winner_code ?? item.winner_name ?? undefined,
      winnerColor: item.winner_constructor
        ? (CONSTRUCTOR_COLORS[item.winner_constructor] ?? '#6b7280')
        : undefined,
    };
  });
}

export function buildWinnerCounts(items: ApiAccuracyItem[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    const code = item.winner_code ?? item.winner_name;
    if (!code) continue;
    counts[code] = (counts[code] ?? 0) + 1;
  }
  return counts;
}

export function buildLearningCurveData(versions: ApiModelVersionItem[]): LearningCurvePoint[] {
  return versions
    .filter((v) => v.round != null && v.mae != null)
    .sort((a, b) => a.round! - b.round!)
    .map((v) => ({ round: v.round!, mae: v.mae! }));
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
