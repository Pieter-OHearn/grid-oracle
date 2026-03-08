import { useState } from 'react';
import { motion } from 'motion/react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, Cell, Legend
} from 'recharts';
import { RACES, RACE_ACCURACY, DRIVERS, RACE_RESULTS, CONSTRUCTOR_COLORS, SEASON_CHART_DATA } from '../data/mockData';
import { BarChart2, TrendingUp, Target, Zap, Award } from 'lucide-react';
import { useNavigate } from 'react-router';

const completedRaces = RACES.filter(r => r.status === 'completed');

// Build season winner standings from results
const winnerCounts: Record<string, number> = {};
completedRaces.forEach(race => {
  const results = RACE_RESULTS[race.id];
  if (results) {
    const winner = results.find(r => r.position === 1);
    if (winner) {
      winnerCounts[winner.driverId] = (winnerCounts[winner.driverId] ?? 0) + 1;
    }
  }
});

const seasonAvgTop3 = Math.round(completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.top3Accuracy ?? 0), 0) / completedRaces.length);
const seasonAvgExact = Math.round(completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.exactHitRate ?? 0), 0) / completedRaces.length);
const seasonAvgMPE = (completedRaces.reduce((s, r) => s + (RACE_ACCURACY[r.id]?.meanPositionError ?? 0), 0) / completedRaces.length).toFixed(2);
const bestRace = completedRaces.reduce((best, r) => {
  const acc = RACE_ACCURACY[r.id]?.top3Accuracy ?? 0;
  return acc > (RACE_ACCURACY[best?.id]?.top3Accuracy ?? 0) ? r : best;
}, completedRaces[0]);

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-[#6b7280] text-[10px] uppercase tracking-wider mb-1.5" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
        {label}
      </p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 mb-0.5">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-[#9090a8] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {p.name}:
          </span>
          <span className="text-white text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
            {typeof p.value === 'number' ? (p.dataKey === 'mpe' ? p.value.toFixed(1) : `${p.value}%`) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
};

const MPETooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-[#6b7280] text-[10px] mb-1" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>{label}</p>
      <span className="text-white text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {payload[0]?.value?.toFixed(1)} avg positions off
      </span>
    </div>
  );
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [activeMetric, setActiveMetric] = useState<'accuracy' | 'error'>('accuracy');

  const summaryStats = [
    { label: 'Races Analysed', value: completedRaces.length.toString(), icon: '🏎️', color: '#e10600', sub: 'of 24 total' },
    { label: 'Avg Podium Accuracy', value: `${seasonAvgTop3}%`, icon: '🏆', color: '#FFD700', sub: 'top 3 correct' },
    { label: 'Avg Exact Hit Rate', value: `${seasonAvgExact}%`, icon: '⚡', color: '#22c55e', sub: 'exact position' },
    { label: 'Avg Position Error', value: seasonAvgMPE, icon: '📐', color: '#f97316', sub: 'positions off' },
    { label: 'Best Race', value: bestRace?.shortName ?? '—', icon: '🎯', color: '#3b82f6', sub: '100% podium' },
  ];

  const exactHitData = SEASON_CHART_DATA.map(d => ({
    ...d,
    fill: d.exactHit >= 25 ? '#22c55e' : d.exactHit >= 15 ? '#eab308' : '#ef4444',
  }));

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-3 mb-6"
      >
        <div className="w-8 h-8 rounded-lg bg-[#e10600]/15 border border-[#e10600]/30 flex items-center justify-center">
          <BarChart2 size={15} className="text-[#e10600]" />
        </div>
        <div>
          <h1 className="text-white" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.5rem', fontWeight: 800, lineHeight: 1.1 }}>
            Season Accuracy Dashboard
          </h1>
          <p className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            2025 F1 Season · Rounds 1–{completedRaces.length} completed
          </p>
        </div>
      </motion.div>

      {/* Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6"
      >
        {summaryStats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.08 + i * 0.05 }}
            className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center hover:border-[#2a2a40] transition-colors"
          >
            <div className="text-xl mb-1">{s.icon}</div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '1.7rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>
              {s.value}
            </div>
            <div className="text-[#3a3a52] text-[10px] mt-1 uppercase tracking-wider" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
              {s.label}
            </div>
            <div className="text-[#2e2e45] text-[9px] mt-0.5" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {s.sub}
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Chart 1: Accuracy Trend */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
        className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 mb-4"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <TrendingUp size={13} className="text-[#e10600]" />
            <h2 className="text-xs uppercase tracking-wider text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}>
              Prediction Accuracy — Race by Race
            </h2>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveMetric('accuracy')}
              className={`px-3 py-1 rounded text-[10px] uppercase tracking-wider transition-all ${activeMetric === 'accuracy' ? 'bg-[#e10600] text-white' : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'}`}
              style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
            >
              Accuracy
            </button>
            <button
              onClick={() => setActiveMetric('error')}
              className={`px-3 py-1 rounded text-[10px] uppercase tracking-wider transition-all ${activeMetric === 'error' ? 'bg-[#e10600] text-white' : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'}`}
              style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
            >
              Error
            </button>
          </div>
        </div>

        <div className="h-52">
          {activeMetric === 'accuracy' ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={SEASON_CHART_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
                <CartesianGrid key="acc-grid" strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
                <XAxis
                  key="acc-xaxis"
                  dataKey="race"
                  tick={{ fill: '#4a4a62', fontSize: 10, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                  axisLine={{ stroke: '#1e1e30' }}
                  tickLine={false}
                />
                <YAxis
                  key="acc-yaxis"
                  domain={[0, 100]}
                  tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={v => `${v}%`}
                />
                <Tooltip key="acc-tooltip" content={<CustomTooltip />} />
                <Legend
                  key="acc-legend"
                  wrapperStyle={{ fontSize: 10, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, color: '#6b7280', paddingTop: 8 }}
                  iconType="circle"
                  iconSize={6}
                />
                <Line
                  key="acc-line-top3"
                  type="monotone"
                  dataKey="top3"
                  name="Podium Accuracy"
                  stroke="#FFD700"
                  strokeWidth={2}
                  dot={{ fill: '#FFD700', r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#FFD700' }}
                />
                <Line
                  key="acc-line-top10"
                  type="monotone"
                  dataKey="top10"
                  name="Top 10 Accuracy"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: '#3b82f6', r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#3b82f6' }}
                />
                <Line
                  key="acc-line-exact"
                  type="monotone"
                  dataKey="exactHit"
                  name="Exact Hit Rate"
                  stroke="#22c55e"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                  dot={{ fill: '#22c55e', r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#22c55e' }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={SEASON_CHART_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
                <CartesianGrid key="mpe-grid" strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
                <XAxis
                  key="mpe-xaxis"
                  dataKey="race"
                  tick={{ fill: '#4a4a62', fontSize: 10, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                  axisLine={{ stroke: '#1e1e30' }}
                  tickLine={false}
                />
                <YAxis
                  key="mpe-yaxis"
                  domain={[0, 5]}
                  tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip key="mpe-tooltip" content={<MPETooltip />} />
                <ReferenceLine key="mpe-ref-good" y={2.0} stroke="#22c55e" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Good', fill: '#22c55e', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
                <ReferenceLine key="mpe-ref-poor" y={3.5} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Poor', fill: '#ef4444', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
                <Line
                  key="mpe-line"
                  type="monotone"
                  dataKey="mpe"
                  name="Mean Position Error"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={{ fill: '#f97316', r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6, fill: '#f97316' }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </motion.div>

      {/* Chart 2: Exact Hit Rate Bar */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.15 }}
        className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 mb-4"
      >
        <div className="flex items-center gap-2 mb-5">
          <Zap size={13} className="text-[#22c55e]" />
          <h2 className="text-xs uppercase tracking-wider text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}>
            Exact Hit Rate per Race
          </h2>
          <span className="text-[10px] text-[#3a3a52] ml-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            (% of positions predicted exactly correct)
          </span>
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={exactHitData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }} barSize={22}>
              <CartesianGrid key="bar-grid" strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
              <XAxis
                key="bar-xaxis"
                dataKey="race"
                tick={{ fill: '#4a4a62', fontSize: 10, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                axisLine={{ stroke: '#1e1e30' }}
                tickLine={false}
              />
              <YAxis
                key="bar-yaxis"
                domain={[0, 40]}
                tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={v => `${v}%`}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
                      <p className="text-[#6b7280] text-[10px] mb-1" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>{label}</p>
                      <span className="text-white text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {payload[0]?.value}% exact positions
                      </span>
                    </div>
                  );
                }}
              />
              <Bar dataKey="exactHit" radius={[3, 3, 0, 0]}>
                {exactHitData.map((entry, index) => (
                  <Cell key={index} fill={entry.fill} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Per-race breakdown table */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.2 }}
        className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl overflow-hidden"
      >
        <div className="flex items-center gap-2 px-5 py-4 border-b border-[#1e1e30]">
          <Target size={13} className="text-[#e10600]" />
          <h2 className="text-xs uppercase tracking-wider text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}>
            Per-Race Breakdown
          </h2>
        </div>

        {/* Table header */}
        <div className="grid grid-cols-[32px_1fr_90px_90px_90px_90px_80px] gap-4 px-5 py-2.5 border-b border-[#1e1e30]">
          {['#', 'RACE', 'PODIUM', 'TOP 10', 'EXACT', 'MPE', 'WINNER'].map((h) => (
            <span key={h} className="text-[10px] uppercase tracking-wider text-[#3a3a52]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
              {h}
            </span>
          ))}
        </div>

        {completedRaces.map((race, idx) => {
          const acc = RACE_ACCURACY[race.id];
          const results = RACE_RESULTS[race.id];
          const winner = results?.find(r => r.position === 1);
          const winnerDriver = winner ? DRIVERS[winner.driverId] : null;
          const winnerColor = winnerDriver ? CONSTRUCTOR_COLORS[winnerDriver.constructor] : '#6b7280';

          return (
            <motion.div
              key={race.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.25, delay: 0.25 + idx * 0.03 }}
              onClick={() => navigate(`/race/${race.id}/results`)}
              className="grid grid-cols-[32px_1fr_90px_90px_90px_90px_80px] gap-4 px-5 py-3 border-b border-[#1a1a28] hover:bg-[#131320] cursor-pointer transition-colors group"
            >
              <span className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {String(race.round).padStart(2, '0')}
              </span>
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-base">{race.countryFlag}</span>
                <span className="text-white text-sm truncate group-hover:text-[#e10600] transition-colors" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                  {race.shortName} — {race.country}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-1 flex-1 bg-[#1e1e30] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${acc?.top3Accuracy ?? 0}%`, background: acc?.top3Accuracy === 100 ? '#22c55e' : acc?.top3Accuracy >= 67 ? '#eab308' : '#ef4444' }} />
                </div>
                <span className="text-white text-xs flex-shrink-0" style={{ fontFamily: "'JetBrains Mono', monospace", color: acc?.top3Accuracy === 100 ? '#22c55e' : acc?.top3Accuracy >= 67 ? '#eab308' : '#ef4444' }}>
                  {acc?.top3Accuracy}%
                </span>
              </div>
              <span className="text-white text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: (acc?.top10Accuracy ?? 0) >= 70 ? '#22c55e' : '#eab308' }}>
                {acc?.top10Accuracy}%
              </span>
              <span className="text-white text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: (acc?.exactHitRate ?? 0) >= 25 ? '#22c55e' : (acc?.exactHitRate ?? 0) >= 15 ? '#eab308' : '#ef4444' }}>
                {acc?.exactHitRate}%
              </span>
              <span className="text-white text-xs" style={{ fontFamily: "'JetBrains Mono', monospace", color: (acc?.meanPositionError ?? 99) <= 2 ? '#22c55e' : (acc?.meanPositionError ?? 99) <= 3 ? '#eab308' : '#ef4444' }}>
                {acc?.meanPositionError.toFixed(1)}
              </span>
              {winnerDriver && (
                <div className="flex items-center gap-1.5 min-w-0">
                  <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: winnerColor }} />
                  <span className="text-[#9090a8] text-[10px] truncate" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
                    {winnerDriver.shortName}
                  </span>
                </div>
              )}
            </motion.div>
          );
        })}
      </motion.div>

      {/* Wins tally */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.3 }}
        className="mt-4 bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5"
      >
        <div className="flex items-center gap-2 mb-4">
          <Award size={13} className="text-[#FFD700]" />
          <h2 className="text-xs uppercase tracking-wider text-[#6b7280]" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}>
            Race Wins So Far
          </h2>
        </div>
        <div className="flex flex-wrap gap-3">
          {Object.entries(winnerCounts)
            .sort((a, b) => b[1] - a[1])
            .map(([driverId, wins]) => {
              const driver = DRIVERS[driverId];
              if (!driver) return null;
              const teamColor = CONSTRUCTOR_COLORS[driver.constructor] ?? '#6b7280';
              return (
                <div key={driverId} className="flex items-center gap-2 px-3 py-2 bg-[#131320] border border-[#1e1e30] rounded-lg">
                  <div className="w-2 h-2 rounded-full" style={{ background: teamColor }} />
                  <span className="text-white text-xs" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
                    {driver.shortName}
                  </span>
                  <span className="text-[#3a3a52] text-[10px]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {driver.constructor}
                  </span>
                  <span className="text-[#FFD700] ml-1" style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: '0.9rem', fontWeight: 800 }}>
                    {wins}W
                  </span>
                </div>
              );
            })}
        </div>
      </motion.div>
    </div>
  );
}