import {
  CONFIDENCE_HIGH,
  CONFIDENCE_STRONG,
  CONFIDENCE_MODERATE,
  CONFIDENCE_LOW,
} from './thresholds';

export const PODIUM_ORDER = [1, 0, 2];
export const MEDAL_COLORS = ['#FFD700', '#C0C0C0', '#CD7F32'];

export function getConfidenceColor(confidence: number): string {
  if (confidence >= CONFIDENCE_HIGH) return '#22c55e';
  if (confidence >= CONFIDENCE_STRONG) return '#84cc16';
  if (confidence >= CONFIDENCE_MODERATE) return '#eab308';
  if (confidence >= CONFIDENCE_LOW) return '#f97316';
  return '#ef4444';
}

export function getConfidenceLabel(confidence: number): string {
  if (confidence >= CONFIDENCE_HIGH) return 'HIGH';
  if (confidence >= CONFIDENCE_STRONG) return 'STRONG';
  if (confidence >= CONFIDENCE_MODERATE) return 'MODERATE';
  if (confidence >= CONFIDENCE_LOW) return 'LOW';
  return 'VERY LOW';
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
