import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ApiDriverItem } from '../services/api';
import { api } from '../services/api';
import { useRaceList } from './RaceListContext';
import type { Driver } from '../types';

function toDriver(item: ApiDriverItem): Driver {
  return {
    code: item.code,
    name: item.full_name,
    shortName: item.code,
    number: item.number,
    constructor: item.constructor,
    nationality: item.nationality,
    flag: item.flag,
    constructorColor: item.constructor_color,
  };
}

type RoundKey = number | null;

interface DriversContextValue {
  getDriver: (code: string, season?: number, round?: number) => Driver | undefined;
  ensureDrivers: (season: number, round?: number) => void;
  isLoading: (season: number, round?: number) => boolean;
}

const DriversContext = createContext<DriversContextValue>({
  getDriver: () => undefined,
  ensureDrivers: () => {},
  isLoading: () => false,
});

// eslint-disable-next-line react-refresh/only-export-components
export function useDrivers() {
  return useContext(DriversContext);
}

function makeKey(season: number, round?: number): string {
  return `${season}:${round ?? 'latest'}`;
}

function roundKey(round?: number): RoundKey {
  return round ?? null;
}

export function DriversProvider({ children }: { children: React.ReactNode }) {
  const { currentSeason } = useRaceList();
  const [driversBySeason, setDriversBySeason] = useState<
    Map<number, Map<RoundKey, Map<string, Driver>>>
  >(new Map());
  const [loadingKeys, setLoadingKeys] = useState<Set<string>>(new Set());

  const fetchDrivers = useCallback((season: number, round?: number) => {
    const key = makeKey(season, round);
    setLoadingKeys((prev) => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });

    api
      .getDrivers(season, round)
      .then((items) => {
        const map = new Map<string, Driver>();
        for (const item of items) {
          map.set(item.code, toDriver(item));
        }
        setDriversBySeason((prev) => {
          const next = new Map(prev);
          const seasonMap = new Map(next.get(season) ?? new Map());
          seasonMap.set(roundKey(round), map);
          next.set(season, seasonMap);
          return next;
        });
      })
      .catch((err) => {
        console.error('Failed to load drivers', season, round, err);
      })
      .finally(() => {
        setLoadingKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      });
  }, []);

  const ensureDrivers = useCallback(
    (season: number, round?: number) => {
      if (!season) return;
      const key = makeKey(season, round);
      const seasonMap = driversBySeason.get(season);
      if (seasonMap?.has(roundKey(round)) || loadingKeys.has(key)) return;
      fetchDrivers(season, round);
    },
    [driversBySeason, fetchDrivers, loadingKeys],
  );

  useEffect(() => {
    ensureDrivers(currentSeason);
  }, [currentSeason, ensureDrivers]);

  const getDriver = useCallback(
    (code: string, season?: number, round?: number) => {
      const targetSeason = season ?? currentSeason;
      if (!targetSeason) return undefined;
      const seasonMap = driversBySeason.get(targetSeason);
      const roundMap = seasonMap?.get(roundKey(round));
      if (roundMap?.has(code)) {
        return roundMap.get(code);
      }
      const fallback = seasonMap?.get(null);
      return fallback?.get(code);
    },
    [currentSeason, driversBySeason],
  );

  const isLoading = useCallback(
    (season: number, round?: number) => loadingKeys.has(makeKey(season, round)),
    [loadingKeys],
  );

  return (
    <DriversContext.Provider value={{ getDriver, ensureDrivers, isLoading }}>
      {children}
    </DriversContext.Provider>
  );
}
