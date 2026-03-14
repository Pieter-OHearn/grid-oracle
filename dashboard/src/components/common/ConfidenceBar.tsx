import { motion } from 'framer-motion';

interface Props {
  confidence: number;
  color: string;
  delay?: number;
  height?: string;
}

export function ConfidenceBar({ confidence, color, delay = 0, height = 'h-1.5' }: Props) {
  return (
    <div className={`${height} bg-[#1e1e30] rounded-full overflow-hidden`}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${confidence}%` }}
        transition={{ duration: 0.7, delay, ease: 'easeOut' }}
        className="h-full rounded-full"
        style={{ background: `linear-gradient(90deg, ${color}60, ${color})` }}
      />
    </div>
  );
}
