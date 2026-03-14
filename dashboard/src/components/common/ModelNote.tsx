import { Zap, AlertCircle } from 'lucide-react';

interface Props {
  text: string;
  variant?: 'zap' | 'info';
}

export function ModelNote({ text, variant = 'zap' }: Props) {
  const Icon = variant === 'zap' ? Zap : AlertCircle;
  return (
    <div className="mt-6 px-4 py-3 bg-[#0f0f1a] border border-[#1e1e30] rounded-lg flex items-start gap-3">
      <Icon
        size={13}
        className={
          variant === 'zap'
            ? 'text-[#e10600] mt-0.5 flex-shrink-0'
            : 'text-[#6b7280] mt-0.5 flex-shrink-0'
        }
      />
      <p className="text-[#3a3a52] text-xs" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {text}
      </p>
    </div>
  );
}
