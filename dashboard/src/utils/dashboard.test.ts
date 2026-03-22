import { describe, expect, it } from 'vitest';

import { buildBreakdownRows, buildChartData, buildSummaryStats } from './dashboard';
import type { ApiAccuracyItem, ApiRaceListItem } from '../services/api';

const accuracyItems: ApiAccuracyItem[] = [
  {
    race_id: 1,
    race_name: 'Bahrain Grand Prix',
    evaluated_at: '2024-03-03T10:00:00Z',
    top3_accuracy: 1,
    top5_accuracy: 0.8,
    top10_accuracy: 0.6,
    exact_position_accuracy: 0.4,
    mean_position_error: 1.2,
    winner_name: 'Max Verstappen',
    winner_code: 'VER',
    winner_constructor: 'Red Bull',
  },
];

const raceList: ApiRaceListItem[] = [
  {
    id: 1,
    round: 1,
    name: 'Bahrain Grand Prix',
    circuit: 'Bahrain International Circuit',
    city: 'Sakhir',
    country: 'Bahrain',
    date: '2024-03-02',
    is_completed: true,
  },
];

describe('dashboard utils', () => {
  it('maps persisted top-10 accuracy into chart and breakdown rows', () => {
    expect(buildChartData(accuracyItems)[0]).toMatchObject({
      race: 'BAH',
      round: 1,
      top3: 100,
      top10: 60,
      exactHit: 40,
      mpe: 1.2,
    });

    expect(buildBreakdownRows(accuracyItems, raceList)[0]).toMatchObject({
      raceId: 1,
      round: 1,
      shortName: 'BAH',
      top3Accuracy: 100,
      top10Accuracy: 60,
      exactHitRate: 40,
      meanPositionError: 1.2,
      winnerShortName: 'VER',
      winnerColor: '#3671C6',
    });
  });

  it('keeps the summary stats at five cards', () => {
    const stats = buildSummaryStats(accuracyItems, 24);

    expect(stats).toHaveLength(5);
    expect(stats.map((stat) => stat.label)).toEqual([
      'Races Analysed',
      'Avg Podium Accuracy',
      'Avg Exact Hit Rate',
      'Avg Position Error',
      'Best Race',
    ]);
  });
});
