import { lazy, Suspense } from 'react';
import PublicApp from './public/PublicApp';
const LegacyApp = lazy(() => import('./LegacyApp'));
export default function App() {
  return import.meta.env.VITE_GRIDORACLE_LEGACY_UI === '1' ? (
    <Suspense fallback={<p>Loading legacy view</p>}>
      <LegacyApp />
    </Suspense>
  ) : (
    <PublicApp />
  );
}
