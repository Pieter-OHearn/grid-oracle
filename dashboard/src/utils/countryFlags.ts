const FLAGS: Record<string, string> = {
  Australia: '🇦🇺',
  Austria: '🇦🇹',
  Azerbaijan: '🇦🇿',
  Bahrain: '🇧🇭',
  Belgium: '🇧🇪',
  Brazil: '🇧🇷',
  Canada: '🇨🇦',
  China: '🇨🇳',
  France: '🇫🇷',
  Germany: '🇩🇪',
  Hungary: '🇭🇺',
  Italy: '🇮🇹',
  Japan: '🇯🇵',
  Mexico: '🇲🇽',
  Monaco: '🇲🇨',
  Netherlands: '🇳🇱',
  Portugal: '🇵🇹',
  Qatar: '🇶🇦',
  'Saudi Arabia': '🇸🇦',
  Singapore: '🇸🇬',
  Spain: '🇪🇸',
  'United Arab Emirates': '🇦🇪',
  'United States': '🇺🇸',
  'United Kingdom': '🇬🇧',
  'Great Britain': '🇬🇧',
  'Abu Dhabi': '🇦🇪',
};

export function getCountryFlag(country: string): string {
  return FLAGS[country] ?? '🏁';
}
