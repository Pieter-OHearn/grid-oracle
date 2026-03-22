import { describe, expect, it } from 'vitest';

import { computeAccuracy } from './results';
import type { ApiComparisonItem } from '../services/api';

function makeComparisonItem(
  predictedPosition: number,
  finishPosition: number | null,
  positionDelta: number | null,
): ApiComparisonItem {
  return {
    driver: `Driver ${predictedPosition}`,
    driver_code: `D${predictedPosition}`,
    constructor: 'Red Bull',
    predicted_position: predictedPosition,
    confidence_score: 0.5,
    finish_position: finishPosition,
    position_delta: positionDelta,
    status: finishPosition == null ? 'DNF' : 'Finished',
    fastest_lap: false,
  };
}

describe('computeAccuracy', () => {
  it('uses fixed denominators for top-3, top-5, and top-10 accuracy', () => {
    const items = [
      makeComparisonItem(1, 1, 0),
      makeComparisonItem(2, 2, 0),
      makeComparisonItem(6, null, null),
      makeComparisonItem(7, null, null),
      makeComparisonItem(8, null, null),
      makeComparisonItem(9, null, null),
    ];

    expect(computeAccuracy(items)).toMatchObject({
      top3Accuracy: 67,
      top5Accuracy: 40,
      top10Accuracy: 20,
      exactHitRate: 100,
      meanPositionError: 0,
      podiumCorrect: 2,
    });
  });
});
