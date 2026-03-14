import { useState, useEffect } from 'react';
import { useParams, Navigate } from 'react-router';
import { motion } from 'framer-motion';
import { AlertCircle, Target, Zap } from 'lucide-react';
import { RACES, RACE_PREDICTIONS, RACE_RESULTS, RACE_ACCURACY, DRIVER_BY_NAME } from '../data';
import { api } from '../services/api';
import type { ApiComparisonItem } from '../services/api';
import { AccuracyMetricsGrid } from '../components/results/AccuracyMetricsGrid';
import { ComparisonRows } from '../components/results/ComparisonRows';
import { ModelNote } from '../components/common/ModelNote';
import { formatDate } from '../utils/results';
import type { PredictionEntry, ActualResult, AccuracyMetrics } from '../types';

const DELTA_KEY = [
  { label: 'Exact', color: '#22c55e' },
  { label: '±1–2', color: '#eab308' },
  { label: '±3–4', color: '#f97316' },
  { label: '5+', color: '#ef4444' },
];

interface Row {
  result: ActualResult;
  prediction: PredictionEntry | undefined;
  predictedPos: number | null;
  delta: number | null;
}

function computeAccuracy(items: ApiComparisonItem[]): AccuracyMetrics {
  const total = items.length;
  const finished = items.filter((i) => i.finish_position !== null);

  const exactHits = finished.filter((i) => i.position_delta === 0).length;
  const exactHitRate = total > 0 ? Math.round((exactHits / total) * 100) : 0;

  const mpe =
    finished.length > 0
      ? finished.reduce((sum, i) => sum + Math.abs(i.position_delta ?? 0), 0) / finished.length
      : 0;

  const top3Hits = items.filter(
    (i) => i.predicted_position <= 3 && i.finish_position !== null && i.finish_position <= 3,
  ).length;
  const top5Hits = items.filter(
    (i) => i.predicted_position <= 5 && i.finish_position !== null && i.finish_position <= 5,
  ).length;
  const top10Hits = items.filter(
    (i) => i.predicted_position <= 10 && i.finish_position !== null && i.finish_position <= 10,
  ).length;

  const podiumCorrect = finished.filter(
    (i) => i.position_delta === 0 && i.finish_position !== null && i.finish_position <= 3,
  ).length;

  return {
    top3Accuracy: Math.round((top3Hits / 3) * 100),
    top5Accuracy: Math.round((top5Hits / 5) * 100),
    top10Accuracy: Math.round((top10Hits / 10) * 100),
    exactHitRate,
    meanPositionError: parseFloat(mpe.toFixed(2)),
    podiumCorrect,
  };
}

function mapApiToRows(items: ApiComparisonItem[]): Row[] {
  return items.map((item) => {
    const driverId = DRIVER_BY_NAME[item.driver] ?? item.driver;
    const isDnf = item.finish_position === null;
    const result: ActualResult = {
      position: item.finish_position ?? 20,
      driverId,
      fastestLap: item.fastest_lap,
      dnf: isDnf,
      dnfReason: isDnf ? (item.status ?? 'DNF') : undefined,
      time: isDnf ? 'DNF' : (item.status ?? ''),
    };
    const prediction: PredictionEntry = {
      position: item.predicted_position,
      driverId,
      confidence: Math.round((item.confidence_score ?? 0) * 100),
    };
    return {
      result,
      prediction,
      predictedPos: item.predicted_position,
      delta: item.position_delta,
    };
  });
}

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
        // API unavailable — fall back to mock data
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
      {/* Race Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-6"
      >
        <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 flex flex-col md:flex-row gap-4 items-start md:items-center">
          <div className="flex items-center gap-4 flex-1">
            <span className="text-4xl">{race.countryFlag}</span>
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <span
                  className="px-2 py-0.5 bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded text-[10px] uppercase tracking-wider"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                >
                  Race Concluded
                </span>
                <span
                  className="text-[#3a3a52] text-[10px]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  Round {String(race.round).padStart(2, '0')} · {formatDate(race.date)}
                </span>
              </div>
              <h1
                className="text-white"
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: '1.5rem',
                  fontWeight: 800,
                  lineHeight: 1.1,
                }}
              >
                {race.name}
              </h1>
              <p className="text-[#6b7280] text-xs mt-0.5">{race.circuit}</p>
            </div>
          </div>
        </div>
      </motion.div>

      <AccuracyMetricsGrid accuracy={accuracy} />

      {/* Delta Legend */}
      <div className="flex items-center gap-4 mb-4">
        <span
          className="text-[#3a3a52] text-[10px] uppercase tracking-wider"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
        >
          Delta Key:
        </span>
        {DELTA_KEY.map((k) => (
          <div key={k.label} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded"
              style={{ background: `${k.color}40`, border: `1px solid ${k.color}60` }}
            />
            <span
              className="text-[10px] text-[#6b7280]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {k.label}
            </span>
          </div>
        ))}
      </div>

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
