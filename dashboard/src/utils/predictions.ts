export const PODIUM_ORDER = [1, 0, 2];
export const MEDAL_COLORS = ['#FFD700', '#C0C0C0', '#CD7F32'];

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 70) return '#22c55e';
  if (confidence >= 55) return '#84cc16';
  if (confidence >= 40) return '#eab308';
  if (confidence >= 25) return '#f97316';
  return '#ef4444';
}

export function getConfidenceLabel(confidence: number): string {
  if (confidence >= 70) return 'HIGH';
  if (confidence >= 55) return 'STRONG';
  if (confidence >= 40) return 'MODERATE';
  if (confidence >= 25) return 'LOW';
  return 'VERY LOW';
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
