import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { ChartTooltip } from './ChartTooltip';
import { SEASON_CHART_DATA } from '../../data';

export function AccuracyLineChart() {
  const [activeMetric, setActiveMetric] = useState<'accuracy' | 'error'>('accuracy');

  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 mb-4">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <TrendingUp size={13} className="text-[#e10600]" />
          <h2
            className="text-xs uppercase tracking-wider text-[#6b7280]"
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontWeight: 700,
              letterSpacing: '0.1em',
            }}
          >
            Prediction Accuracy — Race by Race
          </h2>
        </div>
        <div className="flex items-center gap-1">
          {(['accuracy', 'error'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setActiveMetric(m)}
              className={`px-3 py-1 rounded text-[10px] uppercase tracking-wider transition-all ${
                activeMetric === m
                  ? 'bg-[#e10600] text-white'
                  : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
              }`}
              style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
            >
              {m === 'accuracy' ? 'Accuracy' : 'Error'}
            </button>
          ))}
        </div>
      </div>

      <div className="h-52">
        {activeMetric === 'accuracy' ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={SEASON_CHART_DATA}
              margin={{ top: 5, right: 10, bottom: 5, left: -20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
              <XAxis
                dataKey="race"
                tick={{
                  fill: '#4a4a62',
                  fontSize: 10,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600,
                }}
                axisLine={{ stroke: '#1e1e30' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend
                wrapperStyle={{
                  fontSize: 10,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600,
                  color: '#6b7280',
                  paddingTop: 8,
                }}
                iconType="circle"
                iconSize={6}
              />
              <Line
                type="monotone"
                dataKey="top3"
                name="Podium Accuracy"
                stroke="#FFD700"
                strokeWidth={2}
                dot={{ fill: '#FFD700', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#FFD700' }}
              />
              <Line
                type="monotone"
                dataKey="top10"
                name="Top 10 Accuracy"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#3b82f6' }}
              />
              <Line
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
            <LineChart
              data={SEASON_CHART_DATA}
              margin={{ top: 5, right: 10, bottom: 5, left: -20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
              <XAxis
                dataKey="race"
                tick={{
                  fill: '#4a4a62',
                  fontSize: 10,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600,
                }}
                axisLine={{ stroke: '#1e1e30' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 5]}
                tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
                      <p
                        className="text-[#6b7280] text-[10px] mb-1"
                        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                      >
                        {label}
                      </p>
                      <span
                        className="text-white text-xs"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {(payload[0]?.value as number)?.toFixed(1)} avg positions off
                      </span>
                    </div>
                  );
                }}
              />
              <ReferenceLine
                y={2.0}
                stroke="#22c55e"
                strokeDasharray="4 2"
                strokeOpacity={0.5}
                label={{
                  value: 'Good',
                  fill: '#22c55e',
                  fontSize: 9,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              />
              <ReferenceLine
                y={3.5}
                stroke="#ef4444"
                strokeDasharray="4 2"
                strokeOpacity={0.5}
                label={{
                  value: 'Poor',
                  fill: '#ef4444',
                  fontSize: 9,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              />
              <Line
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
    </div>
  );
}
