import { useParams, Navigate } from 'react-router';
import { motion } from 'motion/react';
import { RACES, DRIVERS, RACE_PREDICTIONS, RACE_RESULTS, RACE_ACCURACY, CONSTRUCTOR_COLORS, CONSTRUCTOR_SHORT } from '../data/mockData';
import { TrendingUp, TrendingDown, Minus, Zap, Target, AlertCircle } from 'lucide-react';

function getDeltaColor(delta: number): string {
  if (delta === 0) return '#22c55e';
  if (Math.abs(delta) <= 2) return '#eab308';
  if (Math.abs(delta) <= 4) return '#f97316';
  return '#ef4444';
}

function getMatchBg(delta: number): string {
  if (delta === 0) return 'rgba(34,197,94,0.07)';
  if (Math.abs(delta) <= 2) return 'rgba(234,179,8,0.05)';
  if (Math.abs(delta) <= 4) return 'rgba(249,115,22,0.05)';
  return 'rgba(239,68,68,0.05)';
}

function getMatchBorder(delta: number): string {
  if (delta === 0) return 'rgba(34,197,94,0.3)';
  if (Math.abs(delta) <= 2) return 'rgba(234,179,8,0.2)';
  if (Math.abs(delta) <= 4) return 'rgba(249,115,22,0.2)';
  return 'rgba(239,68,68,0.2)';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function ResultsPage() {
  const { raceId } = useParams();
  const race = RACES.find(r => r.id === raceId);

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

  // Build merged comparison rows (by actual result position)
  const rows = results.map(result => {
    const prediction = predictions.find(p => p.driverId === result.driverId);
    const predictedPos = prediction?.position ?? null;
    const delta = predictedPos !== null ? predictedPos - result.position : null;
    return { result, prediction, predictedPos, delta };
  });

  const metrics = [
    { label: 'Podium Accuracy', value: `${accuracy.top3Accuracy}%`, sub: `${accuracy.podiumCorrect}/3 correct`, icon: '🏆', color: '#FFD700' },
    { label: 'Top 5 Accuracy', value: `${accuracy.top5Accuracy}%`, sub: 'Drivers in top 5', icon: '🎯', color: '#22c55e' },
    { label: 'Top 10 Accuracy', value: `${accuracy.top10Accuracy}%`, sub: 'Points positions', icon: '📊', color: '#3b82f6' },
    { label: 'Exact Hit Rate', value: `${accuracy.exactHitRate}%`, sub: 'Perfect position calls', icon: '⚡', color: '#e10600' },
    { label: 'Mean Pos. Error', value: accuracy.meanPositionError.toFixed(1), sub: 'Avg positions off', icon: '📐', color: '#f97316' },
  ];

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
                <span className="px-2 py-0.5 bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                  Race Concluded
                </span>
                <span className="text-[#3a3a52] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  Round {String(race.round).padStart(2, '0')} · {formatDate(race.date)}
                </span>
              </div>
              <h1 className="text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.5rem', fontWeight: 800, lineHeight: 1.1 }}>
                {race.name}
              </h1>
              <p className="text-[#6b7280] text-xs mt-0.5">{race.circuit}</p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Accuracy Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6"
      >
        {metrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.1 + i * 0.05 }}
            className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center"
          >
            <div className="text-xl mb-1">{m.icon}</div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.6rem', fontWeight: 800, color: m.color, lineHeight: 1 }}>
              {m.value}
            </div>
            <div className="text-[#3a3a52] text-[10px] mt-1 uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
              {m.label}
            </div>
            <div className="text-[#4a4a62] text-[9px] mt-0.5" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {m.sub}
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-4">
        <span className="text-[#3a3a52] text-[10px] uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
          Delta Key:
        </span>
        {[
          { label: 'Exact', color: '#22c55e' },
          { label: '±1–2', color: '#eab308' },
          { label: '±3–4', color: '#f97316' },
          { label: '5+', color: '#ef4444' },
        ].map(k => (
          <div key={k.label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded" style={{ background: k.color + '40', border: `1px solid ${k.color}60` }} />
            <span className="text-[10px] text-[#6b7280]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{k.label}</span>
          </div>
        ))}
      </div>

      {/* Column Headers */}
      <div className="grid grid-cols-[1fr_1fr] gap-3 mb-2">
        <div className="flex items-center gap-2 px-4">
          <Target size={12} className="text-[#e10600]" />
          <span className="text-[10px] uppercase tracking-widest text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
            Predicted
          </span>
        </div>
        <div className="flex items-center gap-2 px-4">
          <Zap size={12} className="text-[#22c55e]" />
          <span className="text-[10px] uppercase tracking-widest text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
            Actual Result
          </span>
        </div>
      </div>

      {/* Comparison Rows */}
      <div className="space-y-1.5">
        {rows.map(({ result, prediction, predictedPos, delta }, idx) => {
          const driver = DRIVERS[result.driverId];
          if (!driver) return null;
          const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';
          const d = delta ?? 0;
          const matchBg = getMatchBg(d);
          const matchBorder = getMatchBorder(d);
          const deltaColor = getDeltaColor(d);

          return (
            <motion.div
              key={result.driverId}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.15 + idx * 0.022 }}
              className="grid grid-cols-[1fr_44px_1fr] gap-2 items-center"
            >
              {/* Predicted side */}
              <div
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
                style={{ background: matchBg, borderColor: matchBorder }}
              >
                <span
                  className="flex-shrink-0 w-8 text-center"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1rem', fontWeight: 800, color: predictedPos && predictedPos <= 3 ? ['#FFD700','#C0C0C0','#CD7F32'][predictedPos-1] : '#6b7280' }}
                >
                  {predictedPos ? `P${predictedPos}` : '?'}
                </span>
                <div className="w-px h-6 bg-[#1e1e30]" />
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-1.5 h-5 rounded-sm flex-shrink-0" style={{ background: teamColor }} />
                  <div className="min-w-0">
                    <span className="text-white text-sm block truncate" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.02em' }}>
                      {driver.name}
                    </span>
                    <span className="text-[#4a4a62] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {CONSTRUCTOR_SHORT[driver.constructor]}
                    </span>
                  </div>
                </div>
                {prediction && (
                  <span className="ml-auto text-[10px] flex-shrink-0" style={{ fontFamily: "'JetBrains Mono', monospace", color: '#4a4a62' }}>
                    {prediction.confidence}%
                  </span>
                )}
              </div>

              {/* Delta indicator */}
              <div className="flex flex-col items-center justify-center gap-0.5">
                {d === 0 ? (
                  <Minus size={14} style={{ color: deltaColor }} />
                ) : d > 0 ? (
                  <TrendingDown size={14} style={{ color: deltaColor }} />
                ) : (
                  <TrendingUp size={14} style={{ color: deltaColor }} />
                )}
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.6rem', color: deltaColor, fontWeight: 600 }}>
                  {d === 0 ? '=' : d > 0 ? `+${d}` : `${d}`}
                </span>
              </div>

              {/* Actual side */}
              <div
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
                style={{ background: matchBg, borderColor: matchBorder }}
              >
                <span
                  className="flex-shrink-0 w-8 text-center"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1rem', fontWeight: 800, color: result.position <= 3 ? ['#FFD700','#C0C0C0','#CD7F32'][result.position-1] : '#9090a8' }}
                >
                  {result.dnf ? 'DNF' : `P${result.position}`}
                </span>
                <div className="w-px h-6 bg-[#1e1e30]" />
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <div className="w-1.5 h-5 rounded-sm flex-shrink-0" style={{ background: teamColor }} />
                  <div className="min-w-0">
                    <span className="text-white text-sm block truncate" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.02em' }}>
                      {driver.name}
                    </span>
                    <span className="text-[#4a4a62] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {result.dnf ? (result.dnfReason ?? 'DNF') : result.time}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 ml-auto flex-shrink-0">
                  {result.fastestLap && (
                    <span className="px-1.5 py-0.5 bg-[#a855f7]/20 text-[#a855f7] border border-[#a855f7]/30 rounded text-[9px] uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                      FL
                    </span>
                  )}
                  {result.dnf && (
                    <span className="px-1.5 py-0.5 bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/30 rounded text-[9px] uppercase" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                      DNF
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Model Note */}
      <div className="mt-6 px-4 py-3 bg-[#0f0f1a] border border-[#1e1e30] rounded-lg flex items-start gap-3">
        <AlertCircle size={13} className="text-[#6b7280] mt-0.5 flex-shrink-0" />
        <p className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          Delta = Predicted position minus Actual position · Positive = predicted too high · Negative = predicted too low · Exact match = correct call
        </p>
      </div>
    </div>
  );
}
