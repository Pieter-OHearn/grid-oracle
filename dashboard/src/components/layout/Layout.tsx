import { useState, useEffect } from 'react';
import { Outlet } from 'react-router';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { api } from '../../services/api';
import { RaceListContext, deriveRaceStatus, type AppRace } from '../../context/RaceListContext';
import { getCountryFlag } from '../../utils/countryFlags';

function raceShortName(name: string): string {
  return name.replace(' Grand Prix', '').slice(0, 3).toUpperCase();
}

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [races, setRaces] = useState<AppRace[]>([]);
  const [currentSeason, setCurrentSeason] = useState(0);
  const [racesLoaded, setRacesLoaded] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const seasons = await api.getSeasons();
        if (!seasons.length) {
          setRacesLoaded(true);
          return;
        }
        const latest = seasons[0];
        setCurrentSeason(latest);
        const raw = await api.getRaceList(latest);
        const statuses = deriveRaceStatus(raw);
        setRaces(
          raw.map((r, i) => ({
            ...r,
            status: statuses[i],
            countryFlag: getCountryFlag(r.country),
            shortName: raceShortName(r.name),
          })),
        );
      } catch {
        // API unavailable — races stay empty; pages handle empty state
      } finally {
        setRacesLoaded(true);
      }
    }
    load();
  }, []);

  return (
    <RaceListContext.Provider value={{ races, currentSeason, racesLoaded }}>
      <div
        className="flex h-screen bg-[#08080e] text-white overflow-hidden"
        style={{ fontFamily: "'Barlow', sans-serif" }}
      >
        <Sidebar open={sidebarOpen} />

        <div className="flex-1 flex flex-col h-full overflow-hidden">
          <Header sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </RaceListContext.Provider>
  );
}
