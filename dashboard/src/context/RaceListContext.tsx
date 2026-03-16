import { createContext, useContext } from 'react';
import type { ApiRaceListItem } from '../services/api';

export type RaceStatus = 'completed' | 'next' | 'upcoming';

export interface AppRace extends ApiRaceListItem {
  status: RaceStatus;
  countryFlag: string;
  shortName: string;
}

interface RaceListContextValue {
  races: AppRace[];
  currentSeason: number;
}

export const RaceListContext = createContext<RaceListContextValue>({
  races: [],
  currentSeason: 0,
});

export function useRaceList() {
  return useContext(RaceListContext);
}

export function deriveRaceStatus(races: ApiRaceListItem[]): RaceStatus[] {
  let foundNext = false;
  return races.map((race) => {
    if (race.is_completed) return 'completed';
    if (!foundNext) {
      foundNext = true;
      return 'next';
    }
    return 'upcoming';
  });
}
