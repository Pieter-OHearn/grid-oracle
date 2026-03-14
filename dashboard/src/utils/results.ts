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
