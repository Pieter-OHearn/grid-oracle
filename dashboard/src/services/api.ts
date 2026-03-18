const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface ApiRaceListItem {
  id: number;
  round: number;
  name: string;
  circuit: string;
  city: string;
  country: string;
  date: string;
  is_completed: boolean;
}

export interface ApiDriverItem {
  code: string;
  full_name: string;
  number: number | null;
  constructor: string;
  constructor_color: string;
  nationality: string;
  flag: string;
}

export interface ApiPredictionItem {
  driver: string;
  driver_code: string;
  constructor: string;
  predicted_position: number;
  confidence_score: number | null;
  model_version_id: number;
  model_version_name: string;
}

export interface ApiResultItem {
  driver: string;
  driver_code: string;
  constructor: string;
  finish_position: number | null;
  grid_position: number | null;
  status: string;
}

export interface ApiComparisonItem {
  driver: string;
  driver_code: string;
  constructor: string;
  predicted_position: number;
  confidence_score: number | null;
  finish_position: number | null;
  position_delta: number | null;
  status: string | null;
  fastest_lap: boolean;
}

export interface ApiModelVersionItem {
  id: number;
  trained_at: string;
  mae: number | null;
  round: number | null;
  train_seasons: number[] | null;
}

export interface ApiAccuracyItem {
  race_id: number;
  race_name: string;
  evaluated_at: string;
  top3_accuracy: number | null;
  exact_position_accuracy: number | null;
  mean_position_error: number | null;
  winner_name: string | null;
  winner_code: string | null;
  winner_constructor: string | null;
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSeasons: () => request<number[]>('/seasons'),
  getRaceList: (season: number) => request<ApiRaceListItem[]>(`/races/${season}`),
  getDrivers: (season: number, round?: number) =>
    request<ApiDriverItem[]>(
      round != null ? `/drivers?season=${season}&round=${round}` : `/drivers?season=${season}`,
    ),
  getPredictions: (raceId: number) => request<ApiPredictionItem[]>(`/races/${raceId}/predictions`),
  getResults: (raceId: number) => request<ApiResultItem[]>(`/races/${raceId}/results`),
  getComparison: (raceId: number) => request<ApiComparisonItem[]>(`/races/${raceId}/comparison`),
  getSeasonAccuracy: (season: number) => request<ApiAccuracyItem[]>(`/seasons/${season}/accuracy`),
  getModelVersions: (season: number) =>
    request<ApiModelVersionItem[]>(`/model-versions?season=${season}`),
};
