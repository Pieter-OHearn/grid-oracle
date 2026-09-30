import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DataNotice, SampleNotice, TimingTable } from './components';
import { change, percentage, sampleEntries, total } from './sample';

describe('WP10 honest probability presentation', () => {
  it('keeps all 22 unique entries coherent in both horizons', () => {
    expect(new Set(sampleEntries.map((entry) => entry.id)).size).toBe(22);
    expect(total(sampleEntries, 'pre')).toBe(100);
    expect(total(sampleEntries, 'post')).toBe(100);
  });
  it('never converts missing or empty data into a zero probability or total', () => {
    const missing = { ...sampleEntries[0], post: null };
    expect(percentage(null)).toBe('Unknown');
    expect(percentage(0)).toBe('0%');
    expect(total([], 'post')).toBeNull();
    expect(total([missing], 'post')).toBeNull();
    expect(change(missing)).toBe('Unknown');
    const table = renderToStaticMarkup(<TimingTable entries={[missing]} horizon="post" />);
    expect(table).toContain('Unknown total');
    expect(table).not.toContain('NaN');
  });
  it('keeps missing probabilities visible and unranked in full and limited fields', () => {
    for (const horizon of ['pre', 'post'] as const) {
      const missingField = sampleEntries.map((entry, i) =>
        i === 0 ? { ...entry, [horizon]: null } : entry,
      );
      for (const comparison of [false, true]) {
        const table = renderToStaticMarkup(
          <TimingTable
            entries={missingField}
            horizon={horizon}
            comparison={comparison}
            limit={comparison ? undefined : 5}
          />,
        );
        expect(table).toContain('Incomplete field');
        expect(table).toContain('Unknown probabilities · not ranked');
        const norrisRow = table
          .match(/<tr>.*?<\/tr>/g)
          ?.find((row) => row.includes('<span>Norris</span>'));
        expect(norrisRow).toContain('Unranked');
        expect(norrisRow).toContain('Unknown');
        expect(table).not.toContain('>22</td>');
        expect(table).not.toContain('>01</td>');
        expect(table).toContain('Unknown total');
      }
      // Zero remains a known value, even when a different entry is missing.
      const zero = { ...sampleEntries[1], [horizon]: 0 };
      const mixed = renderToStaticMarkup(
        <TimingTable entries={[missingField[0], zero]} horizon={horizon} />,
      );
      expect(mixed).toContain('0%');
      expect(mixed.indexOf('<span>Piastri</span>')).toBeLessThan(
        mixed.indexOf('Unknown probabilities · not ranked'),
      );
    }
  });
  it('states changes in percentage points and marks every table as synthetic', () => {
    expect(change(sampleEntries[0])).toBe('+6 pp');
    const table = renderToStaticMarkup(
      <TimingTable entries={sampleEntries} horizon="post" comparison />,
    );
    expect(table).toContain('22 entries');
    expect(table).toContain('Not a forecast');
    expect(table).toContain('scope="row"');
    expect(renderToStaticMarkup(<SampleNotice />)).toContain('Not a real forecast');
  });
  it('distinguishes publication absence, transport error, unknown and loading', () => {
    const retry = () => {};
    expect(renderToStaticMarkup(<DataNotice state="unavailable" onRetry={retry} />)).toContain(
      'No published run',
    );
    expect(renderToStaticMarkup(<DataNotice state="error" onRetry={retry} />)).toContain(
      'role="alert"',
    );
    expect(renderToStaticMarkup(<DataNotice state="error" onRetry={retry} />)).toContain(
      'Retry sample',
    );
    expect(renderToStaticMarkup(<DataNotice state="unknown" onRetry={retry} />)).toContain(
      'never converted to zero',
    );
    expect(renderToStaticMarkup(<DataNotice state="loading" onRetry={retry} />)).toContain(
      'No probabilities shown',
    );
  });
});
