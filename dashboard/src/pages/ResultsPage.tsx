import { useParams, Navigate } from 'react-router';
import { motion } from 'framer-motion';
import { Target, Zap } from 'lucide-react';
import { RACES, RACE_PREDICTIONS, RACE_RESULTS, RACE_ACCURACY } from '../data';
import { AccuracyMetricsGrid } from '../components/results/AccuracyMetricsGrid';
import { ComparisonRows } from '../components/results/ComparisonRows';
import { ModelNote } from '../components/common/ModelNote';
import { formatDate } from '../utils/results';

const DELTA_KEY = [
  { label: 'Exact', color: '#22c55e' },
  { label: '±1–2', color: '#eab308' },
  { label: '±3–4', color: '#f97316' },
  { label: '5+', color: '#ef4444' },
];

export function ResultsPage() {
  const { raceId } = useParams();
  const race = RACES.find((r) => r.id === raceId);

  if (!race || race.status !== 'completed') {
    return <Navigate to={`/race/${raceId}`} replace />;
  }

  const predictions = raceId ? RACE_PREDICTIONS[raceId] : null;
  const results = raceId ? RACE_RESULTS[raceId] : null;
  const accuracy = raceId ? RACE_ACCURACY[raceId] : null;

  if (!predictions || !results || !accuracy) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <p className="text-sm">No results data available.</p>
      </div>
    );
  }

  const rows = results.map((result) => {
    const prediction = predictions.find((p) => p.driverId === result.driverId);
    const predictedPos = prediction?.position ?? null;
    const delta = predictedPos !== null ? predictedPos - result.position : null;
    return { result, prediction, predictedPos, delta };
  });

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

      {/* Column Headers — three explicit children to align with the 3-col data rows */}
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
        <div /> {/* spacer for the 44px delta column */}
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
