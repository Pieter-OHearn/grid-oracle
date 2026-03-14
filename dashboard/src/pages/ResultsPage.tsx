import { useState, useEffect } from 'react';
import { useParams, Navigate } from 'react-router';
import { AlertCircle, Target, Zap } from 'lucide-react';
import { RACES, RACE_PREDICTIONS, RACE_RESULTS, RACE_ACCURACY } from '../data';
import { api } from '../services/api';
import { AccuracyMetricsGrid } from '../components/results/AccuracyMetricsGrid';
import { ComparisonRows } from '../components/results/ComparisonRows';
import { RaceResultsHeader } from '../components/results/RaceResultsHeader';
import { DeltaLegend } from '../components/results/DeltaLegend';
import { ModelNote } from '../components/common/ModelNote';
import { computeAccuracy, mapApiToRows } from '../utils/results';
import type { Row, AccuracyMetrics } from '../types';

export function ResultsPage() {
  const { raceId } = useParams();
  const race = RACES.find((r) => r.id === raceId);

  const [rows, setRows] = useState<Row[] | null>(null);
  const [accuracy, setAccuracy] = useState<AccuracyMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!race || race.status !== 'completed') {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const season = new Date(race.date).getFullYear();
        const raceList = await api.getRaceList(season);
        const apiRace = raceList.find((r) => r.date === race.date);
        if (!apiRace) throw new Error('Race not found in API');

        const items = await api.getComparison(apiRace.id);
        if (!cancelled) {
          setRows(mapApiToRows(items));
          setAccuracy(computeAccuracy(items));
        }
      } catch {
        if (!cancelled && raceId) {
          const predictions = RACE_PREDICTIONS[raceId];
          const results = RACE_RESULTS[raceId];
          const acc = RACE_ACCURACY[raceId];
          if (predictions && results) {
            setRows(
              results.map((result) => {
                const prediction = predictions.find((p) => p.driverId === result.driverId);
                const predictedPos = prediction?.position ?? null;
                const delta = predictedPos !== null ? predictedPos - result.position : null;
                return { result, prediction, predictedPos, delta };
              }),
            );
          }
          if (acc) setAccuracy(acc);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [raceId, race]);

  if (!race || race.status !== 'completed') {
    return <Navigate to={`/race/${raceId}`} replace />;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <p className="text-sm">Loading results…</p>
      </div>
    );
  }

  if (!rows || !accuracy) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <div className="text-center">
          <AlertCircle size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">No results data available.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <RaceResultsHeader race={race} />

      <AccuracyMetricsGrid accuracy={accuracy} />

      <DeltaLegend />

      {/* Column Headers */}
      <div className="grid grid-cols-[1fr_44px_1fr] gap-2 mb-2">
        <div className="flex items-center gap-2 px-4">
          <Target size={12} className="text-[#e10600]" />
          <span
            className="text-[10px] uppercase tracking-widest text-[#6b7280]"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
          >
            Predicted
          </span>
        </div>
        <div />
        <div className="flex items-center gap-2 px-4">
          <Zap size={12} className="text-[#22c55e]" />
          <span
            className="text-[10px] uppercase tracking-widest text-[#6b7280]"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
          >
            Actual Result
          </span>
        </div>
      </div>

      <ComparisonRows rows={rows} />

      <ModelNote
        text="Delta = Predicted position minus Actual position · Positive = predicted too high · Negative = predicted too low · Exact match = correct call"
        variant="info"
      />
    </div>
  );
}
