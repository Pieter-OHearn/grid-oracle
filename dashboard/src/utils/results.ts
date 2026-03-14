import type { ApiComparisonItem } from '../services/api';
import { DRIVER_BY_NAME } from '../data';
import type { PredictionEntry, ActualResult, AccuracyMetrics, Row } from '../types';

export function computeAccuracy(items: ApiComparisonItem[]): AccuracyMetrics {
  const finished = items.filter((i) => i.finish_position !== null);

  const exactHits = finished.filter((i) => i.position_delta === 0).length;
  const exactHitRate = finished.length > 0 ? Math.round((exactHits / finished.length) * 100) : 0;

  const mpe =
    finished.length > 0
      ? finished.reduce((sum, i) => sum + Math.abs(i.position_delta ?? 0), 0) / finished.length
      : 0;

  const top3Hits = items.filter(
    (i) => i.predicted_position <= 3 && i.finish_position !== null && i.finish_position <= 3,
  ).length;
  const top5Hits = items.filter(
    (i) => i.predicted_position <= 5 && i.finish_position !== null && i.finish_position <= 5,
  ).length;
  const top10Hits = items.filter(
    (i) => i.predicted_position <= 10 && i.finish_position !== null && i.finish_position <= 10,
  ).length;

  const podiumCorrect = finished.filter(
    (i) => i.position_delta === 0 && i.finish_position !== null && i.finish_position <= 3,
  ).length;

  return {
    top3Accuracy: Math.round((top3Hits / 3) * 100),
    top5Accuracy: Math.round((top5Hits / 5) * 100),
    top10Accuracy: Math.round((top10Hits / 10) * 100),
    exactHitRate,
    meanPositionError: parseFloat(mpe.toFixed(2)),
    podiumCorrect,
  };
}

export function mapApiToRows(items: ApiComparisonItem[]): Row[] {
  return items.map((item) => {
    const driverId = DRIVER_BY_NAME[item.driver] ?? item.driver;
    const isDnf = item.finish_position === null;
    const result: ActualResult = {
      position: item.finish_position ?? 20,
      driverId,
      fastestLap: item.fastest_lap,
      dnf: isDnf,
      dnfReason: isDnf ? (item.status ?? 'DNF') : undefined,
      time: isDnf ? 'DNF' : (item.status ?? ''),
    };
    const prediction: PredictionEntry = {
      position: item.predicted_position,
      driverId,
      confidence: Math.round((item.confidence_score ?? 0) * 100),
    };
    return {
      result,
      prediction,
      predictedPos: item.predicted_position,
      delta: item.position_delta,
    };
  });
}

export function getDeltaBg(delta: number | null): string {
  if (delta === null) return 'rgba(90,90,120,0.06)';
  if (delta === 0) return 'rgba(34,197,94,0.07)';
  if (Math.abs(delta) <= 2) return 'rgba(234,179,8,0.05)';
  if (Math.abs(delta) <= 4) return 'rgba(249,115,22,0.05)';
  return 'rgba(239,68,68,0.05)';
}

export function getDeltaBorder(delta: number | null): string {
  if (delta === null) return 'rgba(90,90,120,0.25)';
  if (delta === 0) return 'rgba(34,197,94,0.3)';
  if (Math.abs(delta) <= 2) return 'rgba(234,179,8,0.2)';
  if (Math.abs(delta) <= 4) return 'rgba(249,115,22,0.2)';
  return 'rgba(239,68,68,0.2)';
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
