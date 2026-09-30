import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

const css = readFileSync(new URL('./tokens.css', import.meta.url), 'utf8');
const tokens = Object.fromEntries(
  [...css.matchAll(/--go-([\w-]+):\s*light-dark\((#[\da-f]+),\s*(#[\da-f]+)\)/g)].map((match) => [
    match[1],
    [match[2], match[3]],
  ]),
);
function luminance(hex) {
  const linear = [1, 3, 5].map((index) => {
    const value = Number.parseInt(hex.slice(index, index + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}
function ratio(a, b) {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}
it('meets normal-text and control/focus contrast in both token themes', () => {
  for (const theme of [0, 1]) {
    for (const foreground of ['ink', 'muted', 'accent']) {
      for (const background of ['surface', 'sidebar', 'subtle', 'highlight']) {
        expect(
          ratio(tokens[foreground][theme], tokens[background][theme]),
          `${foreground} on ${background}, theme ${theme}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
    for (const foreground of ['control-border', 'accent']) {
      for (const background of ['surface', 'sidebar', 'subtle']) {
        expect(ratio(tokens[foreground][theme], tokens[background][theme])).toBeGreaterThanOrEqual(
          3,
        );
      }
    }
  }
});
