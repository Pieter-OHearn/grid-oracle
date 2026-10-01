export const seasonPath = (season: number, journey = 'weekend') => `/seasons/${season}/${journey}`;
export const eventPath = (season: number, id: number, journey = '') =>
  `/seasons/${season}/events/${id}${journey ? `/${journey}` : ''}`;
export function switchSeasonPath(path: string, season: number, search: string) {
  const journey = path.split('/')[3];
  if (journey === 'events' && path.split('/')[4]) {
    const params = new URLSearchParams(search);
    if (path.endsWith('/field')) params.set('view', 'field');
    if (path.endsWith('/sessions')) params.set('view', 'sessions');
    return `${seasonPath(season)}?${params}`;
  }
  return `${seasonPath(season, journey || 'weekend')}${search}`;
}
