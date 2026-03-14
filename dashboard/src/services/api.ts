const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getPredictions: (raceId: string) => request(`/predictions/${raceId}`),
  getResults: (raceId: string) => request(`/results/${raceId}`),
  getRaces: () => request('/races'),
};
