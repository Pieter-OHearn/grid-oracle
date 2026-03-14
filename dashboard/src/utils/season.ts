import { RACES, RACE_ACCURACY, RACE_RESULTS } from '../data';
import type { Race } from '../types';

export const completedRaces: Race[] = RACES.filter((r) => r.status === 'completed');

export const winnerCounts: Record<string, number> = {};
completedRaces.forEach((race) => {
  const results = RACE_RESULTS[race.id];
  if (results) {
    const winner = results.find((r) => r.position === 1);
    if (winner) {
      winnerCounts[winner.driverId] = (winnerCounts[winner.driverId] ?? 0) + 1;
    }
  }
});

export const seasonAvgTop3 = completedRaces.length
  ? Math.round(
      completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.top3Accuracy ?? 0), 0) /
        completedRaces.length,
    )
  : 0;

export const seasonAvgExact = completedRaces.length
  ? Math.round(
      completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.exactHitRate ?? 0), 0) /
        completedRaces.length,
    )
  : 0;

export const seasonAvgMPE = completedRaces.length
  ? (
      completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.meanPositionError ?? 0), 0) /
      completedRaces.length
    ).toFixed(2)
  : '0.00';

export const bestRace: Race | undefined = completedRaces.length
  ? completedRaces.reduce((best, r) => {
      const acc = RACE_ACCURACY[r.id]?.top3Accuracy ?? 0;
      return acc > (RACE_ACCURACY[best.id]?.top3Accuracy ?? 0) ? r : best;
    }, completedRaces[0])
  : undefined;
