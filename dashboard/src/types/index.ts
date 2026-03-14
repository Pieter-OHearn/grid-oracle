export interface Driver {
  id: string;
  name: string;
  shortName: string;
  number: number;
  constructor: string;
  nationality: string;
  flag: string;
}

export interface Race {
  id: string;
  round: number;
  name: string;
  shortName: string;
  circuit: string;
  country: string;
  countryFlag: string;
  date: string;
  status: 'completed' | 'upcoming' | 'next';
}

export interface PredictionEntry {
  position: number;
  driverId: string;
  confidence: number;
}

export interface ActualResult {
  position: number;
  driverId: string;
  fastestLap: boolean;
  dnf: boolean;
  dnfReason?: string;
  time: string;
}

export interface AccuracyMetrics {
  top3Accuracy: number;
  top5Accuracy: number;
  top10Accuracy: number;
  exactHitRate: number;
  meanPositionError: number;
  podiumCorrect: number;
}

export interface SeasonChartPoint {
  race: string;
  round: number;
  top3: number;
  top10: number;
  exactHit: number;
  mpe: number;
  podiumCorrect: number;
}
