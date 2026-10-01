/* Deterministic browser acceptance against the explicitly synthetic API fixture.
 * NODE_PATH must resolve playwright; no live-provider or production data is used.
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.WP11_PREVIEW_URL || 'http://127.0.0.1:4173';
const evidence = path.resolve(__dirname, '../docs/design/evidence/wp11');
fs.mkdirSync(evidence, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
  const page = await context.newPage();
  const report = { fixture: 'Synthetic WP11 API acceptance database; percentages are test outputs, not real forecasts', preview: base, checks: [], screenshots: [], pageErrors: [] };
  page.on('pageerror', error => report.pageErrors.push(error.message));
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  const record = (name, details = {}) => report.checks.push({ name, passed: true, ...details });
  const screenshot = async name => { await page.screenshot({ path: path.join(evidence, name + '.jpg'), type: 'jpeg', quality: 82, fullPage: true }); report.screenshots.push(name + '.jpg'); };
  const open = async pathname => { await page.goto(base + pathname); await page.getByRole('table').waitFor(); };
  const full = '/seasons/2022/events/2022/field';
  await open(full);
  await page.reload(); await page.getByRole('table').waitFor();
  assert.equal(await page.locator('tbody tr').count(), 22);
  assert.match(await page.locator('tbody').innerText(), /Fixture team 2022/);
  assert.doesNotMatch(await page.locator('body').innerText(), /Current brand|Current roster|Fixture team 2026|NaN/);
  record('Historical deep link survives browser refresh; 22 entries; historical branding only');
  assert(!requests.some(url => /Distribution-/.test(url)));
  record('Visualization module absent before explicit chart request');
  await screenshot('desktop-full-field');
  await page.getByRole('button', { name: 'Show probability chart' }).click();
  await page.getByRole('heading', { name: 'Published win probability distribution' }).waitFor();
  assert(requests.some(url => /Distribution-/.test(url)));
  record('Large visualization requested lazily');
  await page.getByRole('button', { name: 'Hide probability chart' }).click();
  await page.emulateMedia({ colorScheme: 'dark' }); await screenshot('desktop-dark');
  await page.emulateMedia({ colorScheme: 'light' });

  for (const destination of ['events/2022', 'events/2022/field', 'events/2022/sessions', 'events', 'record', 'methodology', 'sources']) {
    await page.goto(base + '/seasons/2022/' + destination);
    if (destination.includes('sessions')) await page.getByRole('heading', { name: 'Session schedule', exact: true }).waitFor();
    else if (destination.includes('events/2022')) await page.getByRole('table').waitFor();
    else await page.locator('h1').waitFor();
    await page.getByRole('combobox', { name: 'Season' }).selectOption('2026');
    await page.waitForURL(/\/seasons\/2026\//);
    if (destination.startsWith('events/2022') && !destination.includes('sessions')) {
      await page.getByRole('table').waitFor();
      assert.match(await page.locator('tbody').innerText(), /Fixture team 2026/);
    }
    assert.doesNotMatch(await page.locator('body').innerText(), /Fixture team 2022|Fixture Driver .*2022/);
    record('Season switch: ' + destination, { url: page.url() });
  }
  await page.goto(base + '/race/2022'); await page.getByRole('table').waitFor();
  assert.equal(new URL(page.url()).pathname, '/seasons/2022/events/2022');
  record('Legacy link resolves its actual season without current-season fallback');
  await page.goto(base + '/race/2022/results');
  await page.getByRole('heading', { name: 'Results view unavailable' }).waitFor();
  assert.equal(new URL(page.url()).pathname, '/seasons/2022/events/2022/results');
  record('Legacy result link preserves event with explicit unavailable view');
  await page.goto(base + '/race/999');
  await page.getByText('Legacy race not found').waitFor();
  assert.equal(new URL(page.url()).pathname, '/race/999');
  record('Unknown legacy ID remains explicit not-found');

  await open(full);
  await page.getByRole('button', { name: /After qualifying/ }).click();
  await page.getByRole('heading', { name: 'No published forecast' }).waitFor();
  assert.equal(await page.getByRole('table').count(), 0);
  await screenshot('absent-forecast'); record('Absent publication is distinct from request failure');
  await page.route('**/forecast?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'api_unavailable', message: 'Acceptance fixture: API unavailable', retryable: true } }) }));
  await page.reload(); await page.getByRole('alert').waitFor();
  await screenshot('api-unavailable');
  assert.equal(await page.getByRole('button', { name: 'Retry', exact: true }).count(), 1);
  await page.unroute('**/forecast?*');
  await page.getByRole('button', { name: 'Retry', exact: true }).focus(); await page.keyboard.press('Enter');
  await page.getByRole('heading', { name: 'No published forecast' }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement.tagName), 'H1');
  record('API unavailable produces Retry; keyboard retry restores destination focus');

  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/forecast?*', async route => { await pending; await route.continue(); });
  await page.reload(); await page.getByRole('heading', { name: 'Loading selected data' }).waitFor();
  assert.equal(await page.getByRole('table').count(), 0);
  await screenshot('loading'); release();
  await page.getByRole('heading', { name: 'No published forecast' }).waitFor();
  await page.unroute('**/forecast?*');
  record('Loading exposes no retained percentages');

  const actual = await (await context.request.get(base + '/api/v1/seasons/2022/events/2022/forecast?horizon=pre_weekend')).json();
  for (const variant of ['empty', 'unknown']) {
    const body = structuredClone(actual);
    if (variant === 'empty') body.run.entries = [];
    else { body.run.entries[0].win_probability = null; body.run.coverage.state = 'partial'; body.run.coverage.available = 21; }
    await page.route('**/forecast?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) }));
    await page.goto(base + full); await page.reload();
    if (variant === 'empty') await page.getByRole('heading', { name: 'No entries available' }).waitFor();
    else await page.getByRole('table').waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), /NaN/);
    if (variant === 'unknown') assert.match(await page.locator('body').innerText(), /Unranked|Unknown/);
    await screenshot(variant); record('Explicit ' + variant + ' UI never invents zero or NaN');
    await page.unroute('**/forecast?*');
  }

  await open(full); await page.reload(); await page.getByRole('table').waitFor();
  await page.getByRole('link', { name: 'Skip to main content' }).focus(); await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'main');
  await page.getByRole('button', { name: /After qualifying/ }).focus(); await page.keyboard.press('Space');
  await page.getByRole('heading', { name: 'No published forecast' }).waitFor();
  await page.getByRole('button', { name: /Pre-weekend/ }).focus(); await page.keyboard.press('Enter');
  await page.getByRole('table').waitFor();
  await page.getByRole('link', { name: 'Season archive', exact: true }).focus(); await page.keyboard.press('Enter');
  await page.getByRole('heading', { name: '2022 season archive' }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement.tagName), 'H1');
  await page.goBack(); await page.getByRole('table').waitFor();
  assert.equal(await page.evaluate(() => document.activeElement.tagName), 'H1');
  record('Keyboard skip, horizon controls, links and browser-history focus');

  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(base + full); await page.getByRole('table').waitFor();
    const geometry = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth, table: document.querySelector('.go-table-wrap').scrollWidth, region: document.querySelector('.go-table-wrap').clientWidth }));
    assert(geometry.page <= geometry.viewport);
    assert(geometry.table > geometry.region);
    assert.equal(await page.locator('.go-sidebar nav a').count(), 5);
    await page.getByRole('region', { name: /Published probabilities/ }).focus();
    await page.keyboard.press('ArrowRight');
    await page.evaluate(() => scrollTo(0, 0));
    await screenshot('mobile-' + width); record('Responsive reflow and keyboard table scrolling: ' + width, geometry);
  }
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    for (const journey of ['events', 'record', 'methodology', 'sources', 'events/2022/sessions']) {
      await page.goto(base + '/seasons/2022/' + journey);
      await page.locator('h1').waitFor();
      const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
      assert(fits);
      record('Reflow: ' + journey + ' at ' + width);
    }
  }
  await page.goto(base + full); await page.getByRole('table').waitFor();
  await page.locator('h1').focus(); await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.activeElement.textContent), 'Season archive');
  await page.keyboard.press('Shift+Tab');
  assert.equal(await page.evaluate(() => document.activeElement.tagName), 'SELECT');
  record('Native Tab and Shift+Tab traversal');
  await page.getByRole('combobox', { name: 'Season' }).selectOption('2026');
  await page.getByRole('table').waitFor();
  assert.match(await page.locator('tbody').innerText(), /Fixture team 2026/);
  record('320px season-switch journey');
  assert.deepEqual(report.pageErrors, []);
  fs.writeFileSync(path.join(evidence, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
  console.log(JSON.stringify({ checks: report.checks.length, screenshots: report.screenshots.length, pageErrors: report.pageErrors }));
})().catch(error => { console.error(error); process.exit(1); });
