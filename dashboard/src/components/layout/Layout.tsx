import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { RACES } from '../../data';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const handleRaceSelect = (id: string) => {
    const race = RACES.find((r) => r.id === id);
    if (!race) return;
    const isResultsPage = location.pathname.includes('/results');
    if (isResultsPage && race.status === 'completed') {
      navigate(`/race/${id}/results`);
    } else {
      navigate(`/race/${id}`);
    }
  };

  return (
    <div
      className="flex h-screen bg-[#08080e] text-white overflow-hidden"
      style={{ fontFamily: "'Barlow', sans-serif" }}
    >
      <Sidebar open={sidebarOpen} />

      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onRaceSelect={handleRaceSelect}
        />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
