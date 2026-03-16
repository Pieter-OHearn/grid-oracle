import { useState, useEffect } from 'react';
import { useParams } from 'react-router';
import { AlertCircle } from 'lucide-react';
import { DRIVER_BY_NAME } from '../data';
import { api } from '../services/api';
import { useRaceList } from '../context/RaceListContext';
import { RaceHero } from '../components/prediction/RaceHero';
import { PodiumPreview } from '../components/prediction/PodiumPreview';
import { FullGridTable } from '../components/prediction/FullGridTable';
import type { PredictionEntry } from '../types';

export function PredictionPage() {
  const { raceId } = useParams();
  const { races } = useRaceList();
  const numericId = raceId != null ? Number(raceId) : undefined;
  const race = numericId != null ? races.find((r) => r.id === numericId) : undefined;
  const [predictions, setPredictions] = useState<PredictionEntry[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (numericId == null) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const apiPreds = await api.getPredictions(numericId!);
        if (!cancelled) {
          setPredictions(
            apiPreds.map((p) => ({
              position: p.predicted_position,
              driverId: DRIVER_BY_NAME[p.driver] ?? p.driver,
              confidence: Math.round((p.confidence_score ?? 0) * 100),
            })),
          );
        }
      } catch {
        if (!cancelled) setPredictions(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [numericId]);

  if (numericId == null || (!loading && !race)) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <div className="text-center">
          <AlertCircle size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Race not found</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <p className="text-sm">Loading predictions…</p>
      </div>
    );
  }

  if (!predictions) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <div className="text-center">
          <AlertCircle size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">No predictions available for this race yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {race && <RaceHero race={race} predictions={predictions} />}
      <PodiumPreview predictions={predictions} />
      <FullGridTable predictions={predictions} />
    </div>
  );
}
