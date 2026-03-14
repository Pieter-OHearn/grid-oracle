import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { Layout } from './components/layout/Layout';
import { PredictionPage } from './pages/PredictionPage';
import { ResultsPage } from './pages/ResultsPage';
import { DashboardPage } from './pages/DashboardPage';
import { RACES } from './data';

const firstRace = RACES[0];

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to={`/race/${firstRace.id}`} replace />} />
          <Route path="race/:raceId" element={<PredictionPage />} />
          <Route path="race/:raceId/results" element={<ResultsPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to={`/race/${firstRace.id}`} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
