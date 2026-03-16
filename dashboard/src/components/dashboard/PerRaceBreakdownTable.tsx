import { motion } from 'framer-motion';
import { Target } from 'lucide-react';
import { useNavigate } from 'react-router';

function podiumColor(pct: number) {
  if (pct === 100) return '#22c55e';
  if (pct >= 67) return '#eab308';
  return '#ef4444';
}

function top10Color(pct: number) {
  return pct >= 70 ? '#22c55e' : '#eab308';
}

function exactColor(pct: number) {
  if (pct >= 25) return '#22c55e';
  if (pct >= 15) return '#eab308';
  return '#ef4444';
}

function mpeColor(mpe: number) {
  if (mpe <= 2) return '#22c55e';
  if (mpe <= 3) return '#eab308';
  return '#ef4444';
}

export interface BreakdownRow {
  raceId: string | number;
  round: number;
  shortName: string;
  country: string;
  countryFlag: string;
  top3Accuracy?: number;
  top10Accuracy?: number;
  exactHitRate?: number;
  meanPositionError?: number;
  winnerShortName?: string;
  winnerColor?: string;
}

interface Props {
  rows: BreakdownRow[];
}

const HEADERS = ['#', 'RACE', 'PODIUM', 'TOP 10', 'EXACT', 'MPE', 'WINNER'];

export function PerRaceBreakdownTable({ rows }: Props) {
  const navigate = useNavigate();
  const showTop10 = rows.some((r) => r.top10Accuracy != null);
  const showWinner = rows.some((r) => r.winnerShortName != null);

  const colTemplate = [
    '32px',
    '1fr',
    '90px',
    showTop10 ? '90px' : null,
    '90px',
    '90px',
    showWinner ? '80px' : null,
  ]
    .filter(Boolean)
    .join(' ');

  const headers = [
    '#',
    'RACE',
    'PODIUM',
    ...(showTop10 ? ['TOP 10'] : []),
    'EXACT',
    'MPE',
    ...(showWinner ? ['WINNER'] : []),
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.2 }}
      className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl overflow-hidden"
    >
      <div className="flex items-center gap-2 px-5 py-4 border-b border-[#1e1e30]">
        <Target size={13} className="text-[#e10600]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          Per-Race Breakdown
        </h2>
      </div>

      <div
        className="grid gap-4 px-5 py-2.5 border-b border-[#1e1e30]"
        style={{ gridTemplateColumns: colTemplate }}
      >
        {headers.map((h) => (
          <span
            key={h}
            className="text-[10px] uppercase tracking-wider text-[#3a3a52]"
            style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
          >
            {h === '#' ? HEADERS[0] : h}
          </span>
        ))}
      </div>

      {rows.map((row, idx) => (
        <motion.div
          key={row.raceId}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.25, delay: 0.25 + idx * 0.03 }}
          onClick={() => navigate(`/race/${row.raceId}/results`)}
          className="grid gap-4 px-5 py-3 border-b border-[#1a1a28] hover:bg-[#131320] cursor-pointer transition-colors group"
          style={{ gridTemplateColumns: colTemplate }}
        >
          <span
            className="text-[#3a3a52] text-xs"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {String(row.round).padStart(2, '0')}
          </span>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-base">{row.countryFlag}</span>
            <span
              className="text-white text-sm truncate group-hover:text-[#e10600] transition-colors"
              style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
            >
              {row.shortName} — {row.country}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-1 flex-1 bg-[#1e1e30] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${row.top3Accuracy ?? 0}%`,
                  background: podiumColor(row.top3Accuracy ?? 0),
                }}
              />
            </div>
            <span
              className="text-xs flex-shrink-0"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: podiumColor(row.top3Accuracy ?? 0),
              }}
            >
              {row.top3Accuracy != null ? `${row.top3Accuracy}%` : '—'}
            </span>
          </div>
          {showTop10 && (
            <span
              className="text-xs"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: top10Color(row.top10Accuracy ?? 0),
              }}
            >
              {row.top10Accuracy != null ? `${row.top10Accuracy}%` : '—'}
            </span>
          )}
          <span
            className="text-xs"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: exactColor(row.exactHitRate ?? 0),
            }}
          >
            {row.exactHitRate != null ? `${row.exactHitRate}%` : '—'}
          </span>
          <span
            className="text-xs"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: mpeColor(row.meanPositionError ?? 99),
            }}
          >
            {row.meanPositionError != null ? row.meanPositionError.toFixed(1) : '—'}
          </span>
          {showWinner && (
            <div className="flex items-center gap-1.5 min-w-0">
              {row.winnerShortName ? (
                <>
                  <div
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: row.winnerColor ?? '#6b7280' }}
                  />
                  <span
                    className="text-[#9090a8] text-[10px] truncate"
                    style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
                  >
                    {row.winnerShortName}
                  </span>
                </>
              ) : (
                <span
                  className="text-[#3a3a52] text-[10px]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  —
                </span>
              )}
            </div>
          )}
        </motion.div>
      ))}
    </motion.div>
  );
}
