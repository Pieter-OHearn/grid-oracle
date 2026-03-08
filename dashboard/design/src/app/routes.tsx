import { createBrowserRouter, Navigate } from 'react-router';
import { Layout } from './components/Layout';
import { PredictionPage } from './pages/PredictionPage';
import { ResultsPage } from './pages/ResultsPage';
import { DashboardPage } from './pages/DashboardPage';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, element: <Navigate to="/race/esp-2025" replace /> },
      { path: 'race/:raceId', Component: PredictionPage },
      { path: 'race/:raceId/results', Component: ResultsPage },
      { path: 'dashboard', Component: DashboardPage },
      { path: '*', element: <Navigate to="/race/esp-2025" replace /> },
    ],
  },
]);
