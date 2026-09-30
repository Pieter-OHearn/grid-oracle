export type Horizon = 'pre' | 'post';
export type DataState = 'ready' | 'loading' | 'unavailable' | 'error' | 'unknown' | 'empty';
export type Journey = 'race' | 'comparison' | 'scorecard' | 'archive' | 'methodology' | 'sources';
export type Entry = {
  id: string;
  name: string;
  team: string;
  color: string;
  pre: number | null;
  post: number | null;
};

const leaders: Entry[] = [
  { id: 'sample-01', name: 'Norris', team: 'McLaren', color: '#b7650b', pre: 22, post: 28 },
  { id: 'sample-02', name: 'Piastri', team: 'McLaren', color: '#b7650b', pre: 25, post: 24 },
  { id: 'sample-03', name: 'Verstappen', team: 'Red Bull', color: '#4576d2', pre: 21, post: 18 },
  { id: 'sample-04', name: 'Leclerc', team: 'Ferrari', color: '#cb4152', pre: 13, post: 12 },
  { id: 'sample-05', name: 'Russell', team: 'Mercedes', color: '#1b827d', pre: 8, post: 8 },
];
// Deliberately fictional remainder; 22 entries, not an assertion about any season roster.
export const sampleEntries: Entry[] = [
  ...leaders,
  ...Array.from({ length: 17 }, (_, i) => ({
    id: `sample-${i + 6}`,
    name: `Sample driver ${String(i + 6).padStart(2, '0')}`,
    team: `Example team ${Math.floor(i / 2) + 1}`,
    color: '#737980',
    pre: i === 16 ? 3 : 0.5,
    post: i === 16 ? 2 : 0.5,
  })),
];
export const horizonLabels: Record<Horizon, string> = {
  pre: 'Pre-weekend',
  post: 'After qualifying',
};
export const sampleTiming = {
  pre: {
    cutoff: '2026-07-02 12:00 UTC',
    issued: '2026-07-02 12:05 UTC',
    freshness: 'Frozen sample · Before first competitive session',
  },
  post: {
    cutoff: '2026-07-04 14:00 UTC',
    issued: '2026-07-04 14:05 UTC',
    freshness: 'Frozen sample · Verified qualifying / grid example',
  },
};
export function total(entries: Entry[], horizon: Horizon): number | null {
  if (entries.length === 0 || entries.some((entry) => entry[horizon] === null)) return null;
  return entries.reduce((sum, entry) => sum + (entry[horizon] ?? 0), 0);
}
export function percentage(value: number | null): string {
  return value === null ? 'Unknown' : `${value}%`;
}
export function change(entry: Entry): string {
  if (entry.pre === null || entry.post === null) return 'Unknown';
  const difference = Math.round((entry.post - entry.pre) * 10) / 10;
  return `${difference > 0 ? '+' : ''}${difference} pp`;
}

export const destinations: { id: Journey; label: string }[] = [
  { id: 'race', label: 'Race weekend' },
  { id: 'comparison', label: 'Full field' },
  { id: 'scorecard', label: 'Track record' },
  { id: 'archive', label: 'Seasons' },
  { id: 'methodology', label: 'Methodology' },
  { id: 'sources', label: 'Data sources' },
];
