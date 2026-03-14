import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';
import { Zap } from 'lucide-react';
import { SEASON_CHART_DATA } from '../../data';

const chartData = SEASON_CHART_DATA.map((d) => ({
  ...d,
  fill: d.exactHit >= 25 ? '#22c55e' : d.exactHit >= 15 ? '#eab308' : '#ef4444',
}));

export function ExactHitBarChart() {
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 mb-4">
      <div className="flex items-center gap-2 mb-5">
        <Zap size={13} className="text-[#22c55e]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: '0.1em' }}
        >
          Exact Hit Rate per Race
        </h2>
        <span
          className="text-[10px] text-[#3a3a52] ml-2"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          (% of positions predicted exactly correct)
        </span>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }} barSize={22}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
            <XAxis
              dataKey="race"
              tick={{ fill: '#4a4a62', fontSize: 10, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
              axisLine={{ stroke: '#1e1e30' }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 40]}
              tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
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
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.fill} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
