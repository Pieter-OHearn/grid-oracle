import { Activity } from 'lucide-react';

export function Logo() {
  return (
    <div className="px-5 py-4 border-b border-[#1e1e30] flex items-center gap-3 flex-shrink-0">
      <div
        className="w-7 h-7 rounded flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #e10600, #ff4444)' }}
      >
        <Activity size={14} className="text-white" />
      </div>
      <span
        className="text-white tracking-widest uppercase"
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: '1rem',
          fontWeight: 700,
          letterSpacing: '0.12em',
        }}
      >
        Grid<span style={{ color: '#e10600' }}>Oracle</span>
      </span>
    </div>
  );
}
