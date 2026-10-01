import type { PublicEntry } from './contract';
export function probability(value: number | null) {
  return value === null
    ? 'Unknown'
    : `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}
export function fieldTotal(entries: PublicEntry[]) {
  if (!entries.length || entries.some((entry) => entry.win_probability === null)) return null;
  return entries.reduce((sum, entry) => sum + entry.win_probability!, 0);
}
