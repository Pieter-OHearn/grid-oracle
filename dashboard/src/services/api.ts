const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface ApiRaceListItem {
  id: number;
  name: string;
  circuit: string;
  date: string;
  is_completed: boolean;
}

export interface ApiPredictionItem {
  driver: string;
  constructor: string;
  predicted_position: number;
  confidence_score: number | null;
}

export interface ApiResultItem {
  driver: string;
  constructor: string;
  finish_position: number | null;
  grid_position: number | null;
  status: string;
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getRaceList: (season: number) => request<ApiRaceListItem[]>(`/races/${season}`),
  getPredictions: (raceId: number) => request<ApiPredictionItem[]>(`/races/${raceId}/predictions`),
  getResults: (raceId: number) => request<ApiResultItem[]>(`/races/${raceId}/results`),
};
