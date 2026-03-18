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

interface DriversContextValue {
  getDriver: (code: string, season?: number) => Driver | undefined;
  ensureSeason: (season: number) => void;
  isLoading: (season: number) => boolean;
}

const DriversContext = createContext<DriversContextValue>({
  getDriver: () => undefined,
  ensureSeason: () => {},
  isLoading: () => false,
});

// eslint-disable-next-line react-refresh/only-export-components
export function useDrivers() {
  return useContext(DriversContext);
}

export function DriversProvider({ children }: { children: React.ReactNode }) {
  const { currentSeason } = useRaceList();
  const [driversBySeason, setDriversBySeason] = useState<Map<number, Map<string, Driver>>>(
    new Map(),
  );
  const [loadingSeasons, setLoadingSeasons] = useState<Set<number>>(new Set());

  const fetchSeason = useCallback((season: number) => {
    setLoadingSeasons((prev) => {
      if (prev.has(season)) return prev;
      const next = new Set(prev);
      next.add(season);
      return next;
    });

    api
      .getDrivers(season)
      .then((items) => {
        const map = new Map<string, Driver>();
        for (const item of items) {
          map.set(item.code, toDriver(item));
        }
        setDriversBySeason((prev) => {
          const next = new Map(prev);
          next.set(season, map);
          return next;
        });
      })
      .catch(() => {
        // Ignore for now; components can retry ensureSeason
      })
      .finally(() => {
        setLoadingSeasons((prev) => {
          const next = new Set(prev);
          next.delete(season);
          return next;
        });
      });
  }, []);

  const ensureSeason = useCallback(
    (season: number) => {
      if (!season) return;
      if (driversBySeason.has(season) || loadingSeasons.has(season)) return;
      fetchSeason(season);
    },
    [driversBySeason, fetchSeason, loadingSeasons],
  );

  useEffect(() => {
    ensureSeason(currentSeason);
  }, [currentSeason, ensureSeason]);

  const getDriver = useCallback(
    (code: string, season?: number) => {
      const targetSeason = season ?? currentSeason;
      if (!targetSeason) return undefined;
      return driversBySeason.get(targetSeason)?.get(code);
    },
    [currentSeason, driversBySeason],
  );

  const isLoading = useCallback((season: number) => loadingSeasons.has(season), [loadingSeasons]);

  return (
    <DriversContext.Provider value={{ getDriver, ensureSeason, isLoading }}>
      {children}
    </DriversContext.Provider>
  );
}
